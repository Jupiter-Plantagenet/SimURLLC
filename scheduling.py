# scheduling.py
import simpy
from utils import get_logger

def preemptive_priority(base_station, device, packet):
    """
    Preemptive priority scheduling algorithm.
    Higher priority (lower priority value) packets can preempt lower priority ones.
    """
    logger = get_logger()
    
    # Check for preemption opportunity
    for rb in base_station.resource_blocks:
        if id(rb) in base_station.active_transmissions:
            active_device, active_packet, start_time, _ = base_station.active_transmissions[id(rb)]
            if active_packet.priority > packet.priority:  # Lower value = higher priority
                # Preempt current transmission
                with rb.resource.request() as req:
                    yield req
                    
                    # Log preemption
                    logger.log(
                        time=base_station.env.now,
                        device_id=active_device.id,
                        packet_id=active_packet.id,
                        event="preempted",
                        latency=base_station.env.now - active_packet.creation_time
                    )
                    
                    # Store the preempted packet for later continuation
                    base_station.preempted_packets[active_packet.id] = (active_device, active_packet)
                    
                    # Remove preempted transmission
                    del base_station.active_transmissions[id(rb)]
                    
                    # Start new transmission
                    SINR = base_station.calculate_SINR(device)
                    rb.current_SINR = SINR
                    data_rate = base_station.channel_model.calculate_data_rate(
                        SINR, rb.subcarriers, rb.slot_duration
                    )
                    
                    # Calculate transmission time
                    transmission_time = packet.size / data_rate if data_rate > 0 else float('inf')
                    
                    # Add to active transmissions
                    base_station.active_transmissions[id(rb)] = (device, packet, base_station.env.now, rb)
                    
                    # Log transmission start
                    logger.log(
                        time=base_station.env.now,
                        device_id=device.id,
                        packet_id=packet.id,
                        event="transmission_start",
                        latency=base_station.env.now - packet.creation_time,
                        sinr=SINR,
                        data_rate=data_rate,
                        expected_duration=transmission_time
                    )
                    
                    # Wait for transmission to complete
                    yield base_station.env.timeout(transmission_time)
                    
                    # Release resource
                    base_station.release_resource(rb, device, packet)
                    
                    return
    
    # No preemption opportunity, try to find an available resource block
    for rb in base_station.resource_blocks:
        if id(rb) not in base_station.active_transmissions:
            with rb.resource.request() as req:
                yield req
                
                # Start transmission
                SINR = base_station.calculate_SINR(device)
                rb.current_SINR = SINR
                data_rate = base_station.channel_model.calculate_data_rate(
                    SINR, rb.subcarriers, rb.slot_duration
                )
                
                # Calculate transmission time
                transmission_time = packet.size / data_rate if data_rate > 0 else float('inf')
                
                # Add to active transmissions
                base_station.active_transmissions[id(rb)] = (device, packet, base_station.env.now, rb)
                
                # Log transmission start
                logger.log(
                    time=base_station.env.now,
                    device_id=device.id,
                    packet_id=packet.id,
                    event="transmission_start",
                    latency=base_station.env.now - packet.creation_time,
                    sinr=SINR,
                    data_rate=data_rate,
                    expected_duration=transmission_time
                )
                
                # Wait for transmission to complete
                yield base_station.env.timeout(transmission_time)
                
                # Release resource
                base_station.release_resource(rb, device, packet)
                
                return
    
    # If no resource block available, add to waiting queue
    base_station.waiting_queue.put(packet)
    
    # Log packet queued
    logger.log(
        time=base_station.env.now,
        device_id=device.id,
        packet_id=packet.id,
        event="queued",
        latency=base_station.env.now - packet.creation_time
    )

def non_preemptive_priority(base_station, device, packet):
    """
    Non-preemptive priority scheduling algorithm.
    Higher priority packets wait for lower priority ones to finish.
    """
    logger = get_logger()
    
    # Find an available resource block
    for rb in base_station.resource_blocks:
        if id(rb) not in base_station.active_transmissions:
            with rb.resource.request() as req:
                yield req
                
                # Start transmission
                SINR = base_station.calculate_SINR(device)
                rb.current_SINR = SINR
                data_rate = base_station.channel_model.calculate_data_rate(
                    SINR, rb.subcarriers, rb.slot_duration
                )
                
                # Calculate transmission time
                transmission_time = packet.size / data_rate if data_rate > 0 else float('inf')
                
                # Add to active transmissions
                base_station.active_transmissions[id(rb)] = (device, packet, base_station.env.now, rb)
                
                # Log transmission start
                logger.log(
                    time=base_station.env.now,
                    device_id=device.id,
                    packet_id=packet.id,
                    event="transmission_start",
                    latency=base_station.env.now - packet.creation_time,
                    sinr=SINR,
                    data_rate=data_rate,
                    expected_duration=transmission_time
                )
                
                # Wait for transmission to complete
                yield base_station.env.timeout(transmission_time)
                
                # Release resource
                base_station.release_resource(rb, device, packet)
                
                return
    
    # If no resource block available, add to waiting queue
    base_station.waiting_queue.put(packet)
    
    # Log packet queued
    logger.log(
        time=base_station.env.now,
        device_id=device.id,
        packet_id=packet.id,
        event="queued",
        latency=base_station.env.now - packet.creation_time
    )

def round_robin(base_station, device, packet):
    """
    Round Robin scheduling algorithm.
    Assigns resource blocks to devices in a circular order.
    """
    logger = get_logger()
    
    # Find an available resource block
    for rb in base_station.resource_blocks:
        if id(rb) not in base_station.active_transmissions:
            with rb.resource.request() as req:
                yield req
                
                # Start transmission
                SINR = base_station.calculate_SINR(device)
                rb.current_SINR = SINR
                data_rate = base_station.channel_model.calculate_data_rate(
                    SINR, rb.subcarriers, rb.slot_duration
                )
                
                # Calculate transmission time
                transmission_time = packet.size / data_rate if data_rate > 0 else float('inf')
                
                # Limit transmission time for fairness (time-slicing)
                max_time_slice = 0.001  # 1ms time slice
                actual_time = min(transmission_time, max_time_slice)
                
                # Log whether this is a full or partial transmission
                is_partial = actual_time < transmission_time
                
                # Add to active transmissions
                base_station.active_transmissions[id(rb)] = (device, packet, base_station.env.now, rb)
                
                # Log transmission start
                logger.log(
                    time=base_station.env.now,
                    device_id=device.id,
                    packet_id=packet.id,
                    event="transmission_start",
                    latency=base_station.env.now - packet.creation_time,
                    sinr=SINR,
                    data_rate=data_rate,
                    expected_duration=transmission_time,
                    actual_allocation=actual_time,
                    is_partial=is_partial
                )
                
                # Wait for time slice to complete
                yield base_station.env.timeout(actual_time)
                
                # For partial transmissions, recalculate remaining size and requeue
                if is_partial:
                    # Calculate transmitted portion
                    transmitted_bits = data_rate * actual_time
                    remaining_bits = packet.size - transmitted_bits
                    
                    if remaining_bits > 0:
                        # Create continuation packet
                        continuation_packet = type(packet)(
                            creation_time=packet.creation_time,
                            source=device,
                            size=remaining_bits,
                            priority=packet.priority,
                            max_latency=packet.max_latency
                        )
                        continuation_packet.id = packet.id  # Keep same ID
                        
                        # Log continuation
                        logger.log(
                            time=base_station.env.now,
                            device_id=device.id,
                            packet_id=packet.id,
                            event="transmission_continued",
                            latency=base_station.env.now - packet.creation_time,
                            remaining_bits=remaining_bits
                        )
                        
                        # Add to waiting queue for next round
                        base_station.waiting_queue.put(continuation_packet)
                        
                        # Release resource without completing metric recording
                        del base_station.active_transmissions[id(rb)]
                        
                        # Check waiting queue
                        if base_station.waiting_queue.items:
                            base_station.env.process(base_station.process_next_packet(rb))
                    else:
                        # Complete transmission if remaining bits <= 0
                        base_station.release_resource(rb, device, packet)
                else:
                    # Complete transmission
                    base_station.release_resource(rb, device, packet)
                
                return
    
    # If no resource block available, add to waiting queue
    base_station.waiting_queue.put(packet)
    
    # Log packet queued
    logger.log(
        time=base_station.env.now,
        device_id=device.id,
        packet_id=packet.id,
        event="queued",
        latency=base_station.env.now - packet.creation_time
    )

def earliest_deadline_first(base_station, device, packet):
    """
    Earliest Deadline First (EDF) scheduling algorithm.
    Assigns resource blocks based on packet deadlines.
    """
    logger = get_logger()
    
    # Find an available resource block
    for rb in base_station.resource_blocks:
        if id(rb) not in base_station.active_transmissions:
            with rb.resource.request() as req:
                yield req
                
                # Start transmission
                SINR = base_station.calculate_SINR(device)
                rb.current_SINR = SINR
                data_rate = base_station.channel_model.calculate_data_rate(
                    SINR, rb.subcarriers, rb.slot_duration
                )
                
                # Calculate transmission time
                transmission_time = packet.size / data_rate if data_rate > 0 else float('inf')
                
                # Check if we'll miss the deadline
                time_to_deadline = packet.deadline - base_station.env.now
                will_miss_deadline = transmission_time > time_to_deadline
                
                # Add to active transmissions
                base_station.active_transmissions[id(rb)] = (device, packet, base_station.env.now, rb)
                
                # Log transmission start
                logger.log(
                    time=base_station.env.now,
                    device_id=device.id,
                    packet_id=packet.id,
                    event="transmission_start",
                    latency=base_station.env.now - packet.creation_time,
                    sinr=SINR,
                    data_rate=data_rate,
                    expected_duration=transmission_time,
                    will_miss_deadline=will_miss_deadline,
                    time_to_deadline=time_to_deadline
                )
                
                # Wait for transmission to complete
                yield base_station.env.timeout(transmission_time)
                
                # Release resource
                base_station.release_resource(rb, device, packet)
                
                return
    
    # If no resource block available, add to waiting queue
    base_station.waiting_queue.put(packet)
    
    # Log packet queued
    logger.log(
        time=base_station.env.now,
        device_id=device.id,
        packet_id=packet.id,
        event="queued",
        latency=base_station.env.now - packet.creation_time
    )

def fiveg_fixed_priority(base_station, device, packet):
    """
    5G Fixed Priority scheduling algorithm.
    Based on QoS Class Identifier (QCI) levels in 5G networks.
    """
    logger = get_logger()
    
    # Map device priority to QCI levels (lower priority number = higher QCI)
    qci_level = min(9, max(1, packet.priority))
    
    # Find an available resource block
    for rb in base_station.resource_blocks:
        if id(rb) not in base_station.active_transmissions:
            with rb.resource.request() as req:
                yield req
                
                # Start transmission
                SINR = base_station.calculate_SINR(device)
                rb.current_SINR = SINR
                data_rate = base_station.channel_model.calculate_data_rate(
                    SINR, rb.subcarriers, rb.slot_duration
                )
                
                # Calculate transmission time based on QCI level
                # Lower QCI levels get more aggressive modulation and coding schemes
                qci_factor = (10 - qci_level) / 10  # QCI 1 = 0.9, QCI 9 = 0.1
                adjusted_data_rate = data_rate * (1 + qci_factor)
                
                transmission_time = packet.size / adjusted_data_rate if adjusted_data_rate > 0 else float('inf')
                
                # Add to active transmissions
                base_station.active_transmissions[id(rb)] = (device, packet, base_station.env.now, rb)
                
                # Log transmission start
                logger.log(
                    time=base_station.env.now,
                    device_id=device.id,
                    packet_id=packet.id,
                    event="transmission_start",
                    latency=base_station.env.now - packet.creation_time,
                    sinr=SINR,
                    data_rate=data_rate,
                    adjusted_data_rate=adjusted_data_rate,
                    qci_level=qci_level,
                    expected_duration=transmission_time
                )
                
                # Wait for transmission to complete
                yield base_station.env.timeout(transmission_time)
                
                # Release resource
                base_station.release_resource(rb, device, packet)
                
                return
    
    # If no resource block available, add to waiting queue
    base_station.waiting_queue.put(packet)
    
    # Log packet queued
    logger.log(
        time=base_station.env.now,
        device_id=device.id,
        packet_id=packet.id,
        event="queued",
        latency=base_station.env.now - packet.creation_time
    )

def hybrid_edf_preemptive(base_station, device, packet):
    """
    Hybrid EDF-Preemptive scheduling algorithm.
    Combines EDF for packets with imminent deadlines and preemptive priority otherwise.
    """
    logger = get_logger()
    
    # Calculate time-to-deadline
    time_to_deadline = packet.deadline - base_station.env.now
    
    # If deadline is imminent (< 0.5ms), use EDF logic
    use_edf = time_to_deadline < 0.0005
    
    if use_edf:
        # EDF mode: prioritize based on imminent deadline
        for rb in base_station.resource_blocks:
            if id(rb) in base_station.active_transmissions:
                active_device, active_packet, start_time, _ = base_station.active_transmissions[id(rb)]
                active_time_to_deadline = active_packet.deadline - base_station.env.now
                
                # Preempt if active packet has more time until deadline
                if active_time_to_deadline > time_to_deadline:
                    with rb.resource.request() as req:
                        yield req
                        
                        # Log preemption
                        logger.log(
                            time=base_station.env.now,
                            device_id=active_device.id,
                            packet_id=active_packet.id,
                            event="preempted_by_edf",
                            latency=base_station.env.now - active_packet.creation_time,
                            active_time_to_deadline=active_time_to_deadline,
                            preempting_time_to_deadline=time_to_deadline
                        )
                        
                        # Store the preempted packet for later continuation
                        base_station.preempted_packets[active_packet.id] = (active_device, active_packet)
                        
                        # Remove preempted transmission
                        del base_station.active_transmissions[id(rb)]
                        
                        # Start new transmission
                        SINR = base_station.calculate_SINR(device)
                        rb.current_SINR = SINR
                        data_rate = base_station.channel_model.calculate_data_rate(
                            SINR, rb.subcarriers, rb.slot_duration
                        )
                        
                        # Calculate transmission time
                        transmission_time = packet.size / data_rate if data_rate > 0 else float('inf')
                        
                        # Add to active transmissions
                        base_station.active_transmissions[id(rb)] = (device, packet, base_station.env.now, rb)
                        
                        # Log transmission start
                        logger.log(
                            time=base_station.env.now,
                            device_id=device.id,
                            packet_id=packet.id,
                            event="transmission_start_edf",
                            latency=base_station.env.now - packet.creation_time,
                            sinr=SINR,
                            data_rate=data_rate,
                            expected_duration=transmission_time,
                            time_to_deadline=time_to_deadline
                        )
                        
                        # Wait for transmission to complete
                        yield base_station.env.timeout(transmission_time)
                        
                        # Release resource
                        base_station.release_resource(rb, device, packet)
                        
                        return
    else:
        # Preemptive mode: use priority-based preemption
        for rb in base_station.resource_blocks:
            if id(rb) in base_station.active_transmissions:
                active_device, active_packet, start_time, _ = base_station.active_transmissions[id(rb)]
                if active_packet.priority > packet.priority:  # Lower value = higher priority
                    with rb.resource.request() as req:
                        yield req
                        
                        # Log preemption
                        logger.log(
                            time=base_station.env.now,
                            device_id=active_device.id,
                            packet_id=active_packet.id,
                            event="preempted_by_priority",
                            latency=base_station.env.now - active_packet.creation_time
                        )
                        
                        # Store the preempted packet for later continuation
                        base_station.preempted_packets[active_packet.id] = (active_device, active_packet)
                        
                        # Remove preempted transmission
                        del base_station.active_transmissions[id(rb)]
                        
                        # Start new transmission
                        SINR = base_station.calculate_SINR(device)
                        rb.current_SINR = SINR
                        data_rate = base_station.channel_model.calculate_data_rate(
                            SINR, rb.subcarriers, rb.slot_duration
                        )
                        
                        # Calculate transmission time
                        transmission_time = packet.size / data_rate if data_rate > 0 else float('inf')
                        
                        # Add to active transmissions
                        base_station.active_transmissions[id(rb)] = (device, packet, base_station.env.now, rb)
                        
                        # Log transmission start
                        logger.log(
                            time=base_station.env.now,
                            device_id=device.id,
                            packet_id=packet.id,
                            event="transmission_start_priority",
                            latency=base_station.env.now - packet.creation_time,
                            sinr=SINR,
                            data_rate=data_rate,
                            expected_duration=transmission_time
                        )
                        
                        # Wait for transmission to complete
                        yield base_station.env.timeout(transmission_time)
                        
                        # Release resource
                        base_station.release_resource(rb, device, packet)
                        
                        return
    
    # No preemption opportunity, try to find an available resource block
    for rb in base_station.resource_blocks:
        if id(rb) not in base_station.active_transmissions:
            with rb.resource.request() as req:
                yield req
                
                # Start transmission
                SINR = base_station.calculate_SINR(device)
                rb.current_SINR = SINR
                data_rate = base_station.channel_model.calculate_data_rate(
                    SINR, rb.subcarriers, rb.slot_duration
                )
                
                # Calculate transmission time
                transmission_time = packet.size / data_rate if data_rate > 0 else float('inf')
                
                # Add to active transmissions
                base_station.active_transmissions[id(rb)] = (device, packet, base_station.env.now, rb)
                
                # Log transmission start
                logger.log(
                    time=base_station.env.now,
                    device_id=device.id,
                    packet_id=packet.id,
                    event="transmission_start",
                    latency=base_station.env.now - packet.creation_time,
                    sinr=SINR,
                    data_rate=data_rate,
                    expected_duration=transmission_time,
                    time_to_deadline=time_to_deadline
                )
                
                # Wait for transmission to complete
                yield base_station.env.timeout(transmission_time)
                
                # Release resource
                base_station.release_resource(rb, device, packet)
                
                return
    
    # If no resource block available, add to waiting queue
    base_station.waiting_queue.put(packet)
    
    # Log packet queued
    logger.log(
        time=base_station.env.now,
        device_id=device.id,
        packet_id=packet.id,
        event="queued",
        latency=base_station.env.now - packet.creation_time
    ) 