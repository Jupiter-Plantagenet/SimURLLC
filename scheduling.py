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
            active_device, active_packet, _, _ = base_station.active_transmissions[id(rb)]
            if active_packet.priority > packet.priority:  # Lower value = higher priority
                # Preempt current transmission
                with rb.resource.request(priority=packet.priority) as req:
                    yield req
                    
                    # Log preemption
                    logger.log(
                        time=base_station.env.now,
                        device_id=active_device.id,
                        packet_id=active_packet.id,
                        event="preempted",
                        latency=base_station.env.now - active_packet.creation_time
                    )
                    
                    # Update active transmissions
                    base_station.active_transmissions[id(rb)] = (device, packet, base_station.env.now, rb)
                    
                    # Calculate transmission time based on packet size and channel conditions
                    rb.current_SINR = base_station.calculate_SINR(device)
                    data_rate = base_station.channel_model.calculate_data_rate(
                        rb.current_SINR, rb.subcarriers, rb.slot_duration)
                    transmission_time = packet.size / data_rate
                    
                    # Simulate transmission
                    yield base_station.env.timeout(transmission_time)
                    
                    # Release resource
                    base_station.release_resource(rb, device, packet)
                    return
    
    # If no preemption possible, try to find free resource block
    for rb in base_station.resource_blocks:
        if id(rb) not in base_station.active_transmissions:
            with rb.resource.request(priority=packet.priority) as req:
                yield req
                
                # Update active transmissions
                base_station.active_transmissions[id(rb)] = (device, packet, base_station.env.now, rb)
                
                # Calculate transmission time
                rb.current_SINR = base_station.calculate_SINR(device)
                data_rate = base_station.channel_model.calculate_data_rate(
                    rb.current_SINR, rb.subcarriers, rb.slot_duration)
                transmission_time = packet.size / data_rate
                
                # Simulate transmission
                yield base_station.env.timeout(transmission_time)
                
                # Release resource
                base_station.release_resource(rb, device, packet)
                return
    
    # If no resource block available, add to waiting queue
    yield base_station.waiting_queue.put(packet)

def non_preemptive_priority(base_station, device, packet):
    """
    Non-preemptive priority scheduling algorithm.
    Higher priority packets wait for lower priority ones to finish.
    """
    # Try to find free resource block
    for rb in base_station.resource_blocks:
        if id(rb) not in base_station.active_transmissions:
            with rb.resource.request(priority=packet.priority) as req:
                yield req
                
                # Update active transmissions
                base_station.active_transmissions[id(rb)] = (device, packet, base_station.env.now, rb)
                
                # Calculate transmission time
                rb.current_SINR = base_station.calculate_SINR(device)
                data_rate = base_station.channel_model.calculate_data_rate(
                    rb.current_SINR, rb.subcarriers, rb.slot_duration)
                transmission_time = packet.size / data_rate
                
                # Simulate transmission
                yield base_station.env.timeout(transmission_time)
                
                # Release resource
                base_station.release_resource(rb, device, packet)
                return
    
    # If no resource block available, add to waiting queue
    yield base_station.waiting_queue.put(packet)

def round_robin(base_station, device, packet):
    """
    Round-robin scheduling algorithm.
    Cycles through devices in a circular order.
    """
    # Try to find free resource block
    for rb in base_station.resource_blocks:
        if id(rb) not in base_station.active_transmissions:
            with rb.resource.request() as req:
                yield req
                
                # Update active transmissions
                base_station.active_transmissions[id(rb)] = (device, packet, base_station.env.now, rb)
                
                # Calculate transmission time
                rb.current_SINR = base_station.calculate_SINR(device)
                data_rate = base_station.channel_model.calculate_data_rate(
                    rb.current_SINR, rb.subcarriers, rb.slot_duration)
                transmission_time = packet.size / data_rate
                
                # Simulate transmission
                yield base_station.env.timeout(transmission_time)
                
                # Release resource
                base_station.release_resource(rb, device, packet)
                return
    
    # If no resource block available, add to waiting queue
    yield base_station.waiting_queue.put(packet)

def earliest_deadline_first(base_station, device, packet):
    """
    Earliest Deadline First (EDF) scheduling algorithm.
    Schedules packets based on their deadlines.
    """
    # Override packet priority with deadline for EDF
    packet.priority = packet.deadline
    
    # Try to find free resource block
    for rb in base_station.resource_blocks:
        if id(rb) not in base_station.active_transmissions:
            with rb.resource.request(priority=packet.deadline) as req:
                yield req
                
                # Update active transmissions
                base_station.active_transmissions[id(rb)] = (device, packet, base_station.env.now, rb)
                
                # Calculate transmission time
                rb.current_SINR = base_station.calculate_SINR(device)
                data_rate = base_station.channel_model.calculate_data_rate(
                    rb.current_SINR, rb.subcarriers, rb.slot_duration)
                transmission_time = packet.size / data_rate
                
                # Simulate transmission
                yield base_station.env.timeout(transmission_time)
                
                # Release resource
                base_station.release_resource(rb, device, packet)
                return
    
    # If no resource block available, add to waiting queue
    yield base_station.waiting_queue.put(packet)

def fiveg_fixed_priority(base_station, device, packet):
    """
    5G-style fixed priority scheduling.
    Similar to non-preemptive but with 5G-specific QoS handling.
    """
    # Calculate 5G QCI (QoS Class Identifier) based priority
    qci_priority = min(packet.priority * 2, 9)  # Map to 5G QCI values (1-9)
    packet.priority = qci_priority
    
    # Try to find free resource block
    for rb in base_station.resource_blocks:
        if id(rb) not in base_station.active_transmissions:
            with rb.resource.request(priority=qci_priority) as req:
                yield req
                
                # Update active transmissions
                base_station.active_transmissions[id(rb)] = (device, packet, base_station.env.now, rb)
                
                # Calculate transmission time
                rb.current_SINR = base_station.calculate_SINR(device)
                data_rate = base_station.channel_model.calculate_data_rate(
                    rb.current_SINR, rb.subcarriers, rb.slot_duration)
                transmission_time = packet.size / data_rate
                
                # Simulate transmission
                yield base_station.env.timeout(transmission_time)
                
                # Release resource
                base_station.release_resource(rb, device, packet)
                return
    
    # If no resource block available, add to waiting queue
    yield base_station.waiting_queue.put(packet)

def hybrid_edf_preemptive(base_station, device, packet):
    """
    Hybrid EDF-Preemptive scheduling algorithm.
    Combines EDF with preemption capabilities.
    """
    logger = get_logger()
    
    # Calculate dynamic priority based on deadline and current time
    urgency = packet.deadline - base_station.env.now
    packet.priority = urgency
    
    # Check for preemption opportunity
    for rb in base_station.resource_blocks:
        if id(rb) in base_station.active_transmissions:
            active_device, active_packet, start_time, _ = base_station.active_transmissions[id(rb)]
            active_urgency = active_packet.deadline - base_station.env.now
            
            if active_urgency > urgency:  # Current packet more urgent
                # Preempt current transmission
                with rb.resource.request(priority=urgency) as req:
                    yield req
                    
                    # Log preemption
                    logger.log(
                        time=base_station.env.now,
                        device_id=active_device.id,
                        packet_id=active_packet.id,
                        event="preempted",
                        latency=base_station.env.now - active_packet.creation_time
                    )
                    
                    # Update active transmissions
                    base_station.active_transmissions[id(rb)] = (device, packet, base_station.env.now, rb)
                    
                    # Calculate transmission time
                    rb.current_SINR = base_station.calculate_SINR(device)
                    data_rate = base_station.channel_model.calculate_data_rate(
                        rb.current_SINR, rb.subcarriers, rb.slot_duration)
                    transmission_time = packet.size / data_rate
                    
                    # Simulate transmission
                    yield base_station.env.timeout(transmission_time)
                    
                    # Release resource
                    base_station.release_resource(rb, device, packet)
                    return
    
    # If no preemption possible, try to find free resource block
    for rb in base_station.resource_blocks:
        if id(rb) not in base_station.active_transmissions:
            with rb.resource.request(priority=urgency) as req:
                yield req
                
                # Update active transmissions
                base_station.active_transmissions[id(rb)] = (device, packet, base_station.env.now, rb)
                
                # Calculate transmission time
                rb.current_SINR = base_station.calculate_SINR(device)
                data_rate = base_station.channel_model.calculate_data_rate(
                    rb.current_SINR, rb.subcarriers, rb.slot_duration)
                transmission_time = packet.size / data_rate
                
                # Simulate transmission
                yield base_station.env.timeout(transmission_time)
                
                # Release resource
                base_station.release_resource(rb, device, packet)
                return
    
    # If no resource block available, add to waiting queue
    yield base_station.waiting_queue.put(packet) 