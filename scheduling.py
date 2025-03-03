# scheduling.py
# This file contains all the scheduling algorithms for SimURLLC. These functions decide
# how the BaseStation assigns resource blocks to devices and packets.

import simpy  # SimPy library for managing simulation events and timeouts
from utils import get_logger  # Import our logger to record events
import numpy as np  # Import numpy

def preemptive_priority(base_station, device, packet):
    # This function implements the Preemptive Priority scheduling algorithm
    # It gives resource blocks to high-priority packets, preempting lower ones if needed
    logger = get_logger()  # Get the logger to record what happens
    # Check if there's an available resource block (RB)
    if len(base_station.active_transmissions) < base_station.num_rbs:
        # If yes, find the first free RB (not in active transmissions)
        rb = next(rb for rb in base_station.resource_blocks 
                  if id(rb) not in base_station.active_transmissions)
        # Calculate the Signal-to-Interference-plus-Noise Ratio (SINR) for this device
        rb.current_SINR = base_station.calculate_SINR(device)
        # Request the RB with the packet's priority (higher number = lower priority in SimPy)
        with rb.resource.request() as req: # No more priority
            yield req  # Wait until the RB is granted
            # Add this transmission to the active list with the device, packet, and start time
            base_station.active_transmissions[id(rb)] = (device, packet, base_station.env.now)
            # Get the data rate based on the SINR
            data_rate = base_station.channel_model.calculate_data_rate(rb.current_SINR)
            # Calculate how long it takes to send the packet (size / (data rate * subcarriers))
            transmission_time = packet.size / (data_rate * rb.subcarriers)
            # Log that transmission is starting
            logger.log(base_station.env.now, device.id, packet.id, "transmission_start", 
                       sinr=rb.current_SINR)
            print(f"Time {base_station.env.now:.3f}: Starting transmission for device {device.id}, packet {packet.id}, SINR: {rb.current_SINR:.2f} dB, data rate: {data_rate/1e6:.2f} Mbps, time: {transmission_time*1000:.2f} ms")
            # Wait for the transmission to finish
            yield base_station.env.timeout(transmission_time)
            # Release the RB when done
            yield base_station.env.process(base_station.release_resource(rb, device, packet))
    else:
        # If no RBs are free, check for preemption
        # Find the lowest priority among active transmissions (highest number = lowest priority)
        min_priority = min(base_station.active_transmissions[rb_id][1].priority 
                          for rb_id in base_station.active_transmissions)
        # If this packet has higher priority (lower number) than the lowest active one
        if packet.priority < min_priority:
            # Find the RB with the lowest priority transmission to preempt
            rb_to_preempt = min(base_station.active_transmissions, 
                               key=lambda rb_id: base_station.active_transmissions[rb_id][1].priority)
            # Get the device and packet being preempted
            preempted_device, preempted_packet, _ = base_station.active_transmissions[rb_to_preempt]
            # Remove the preempted transmission
            del base_station.active_transmissions[rb_to_preempt]
            # Add a 0.1 ms penalty to the preempted packet's time (simulates retransmission cost)
            # Note: This is simplified; in reality, we'd restart its process
            yield base_station.env.timeout(0.1)
            # Use packet.priority for the preempted packet:
            yield base_station.waiting_queue.put((preempted_packet.priority, (preempted_device, preempted_packet)))
            # Now use the freed RB for the new packet
            rb = base_station.resource_blocks[rb_to_preempt]
            rb.current_SINR = base_station.calculate_SINR(device)
            with rb.resource.request() as req: # No more priority
                yield req
                base_station.active_transmissions[id(rb)] = (device, packet, base_station.env.now)
                data_rate = base_station.channel_model.calculate_data_rate(rb.current_SINR)
                transmission_time = packet.size / (data_rate * rb.subcarriers)
                logger.log(base_station.env.now, device.id, packet.id, "transmission_start", 
                           sinr=rb.current_SINR)
                print(f"Time {base_station.env.now:.3f}: Starting transmission for device {device.id}, packet {packet.id}, SINR: {rb.current_SINR:.2f} dB, data rate: {data_rate/1e6:.2f} Mbps, time: {transmission_time*1000:.2f} ms")
                yield base_station.env.timeout(transmission_time)
                yield base_station.env.process(base_station.release_resource(rb, device, packet))
        else:
            # Use packet.priority for the new packet:
            yield base_station.waiting_queue.put((packet.priority, (device, packet)))


def non_preemptive_priority(base_station, device, packet):
    # This function implements Non-Preemptive Priority scheduling
    # It assigns RBs to high-priority packets but doesn't interrupt active ones
    logger = get_logger()
    if len(base_station.active_transmissions) < base_station.num_rbs:
        # If an RB is free, use it (same logic as preemptive without preemption)
        rb = next(rb for rb in base_station.resource_blocks 
                  if id(rb) not in base_station.active_transmissions)
        rb.current_SINR = base_station.calculate_SINR(device)
        with rb.resource.request() as req: # No more priority
            yield req
            base_station.active_transmissions[id(rb)] = (device, packet, base_station.env.now)
            data_rate = base_station.channel_model.calculate_data_rate(rb.current_SINR)
            transmission_time = packet.size / (data_rate * rb.subcarriers)
            logger.log(base_station.env.now, device.id, packet.id, "transmission_start", 
                       sinr=rb.current_SINR)
            print(f"Time {base_station.env.now:.3f}: Starting transmission for device {device.id}, packet {packet.id}, SINR: {rb.current_SINR:.2f} dB, data rate: {data_rate/1e6:.2f} Mbps, time: {transmission_time*1000:.2f} ms")
            yield base_station.env.timeout(transmission_time)
            yield base_station.env.process(base_station.release_resource(rb, device, packet))
    else:
        # Use packet.priority:
        yield base_station.waiting_queue.put((packet.priority, (device, packet)))

def round_robin(base_station, device, packet):
    # This function implements Round-Robin scheduling
    # It assigns RBs in a fair, circular order without priority
    logger = get_logger()
    if len(base_station.active_transmissions) < base_station.num_rbs:
        # If an RB is free, use it
        rb = next(rb for rb in base_station.resource_blocks 
                  if id(rb) not in base_station.active_transmissions)
        rb.current_SINR = base_station.calculate_SINR(device)
        with rb.resource.request() as req: # No more priority
            yield req
            base_station.active_transmissions[id(rb)] = (device, packet, base_station.env.now)
            data_rate = base_station.channel_model.calculate_data_rate(rb.current_SINR)
            transmission_time = packet.size / (data_rate * rb.subcarriers)
            logger.log(base_station.env.now, device.id, packet.id, "transmission_start", 
                       sinr=rb.current_SINR)
            print(f"Time {base_station.env.now:.3f}: Starting transmission for device {device.id}, packet {packet.id}, SINR: {rb.current_SINR:.2f} dB, data rate: {data_rate/1e6:.2f} Mbps, time: {transmission_time*1000:.2f} ms")
            yield base_station.env.timeout(transmission_time)
            yield base_station.env.process(base_station.release_resource(rb, device, packet))
    else:
        # Use env.now as priority (FIFO):
        yield base_station.waiting_queue.put((base_station.env.now, (device, packet)))

def earliest_deadline_first(base_station, device, packet):
    # This function implements Earliest Deadline First (EDF) scheduling
    # It prioritizes packets with the earliest deadlines
    logger = get_logger()
    if len(base_station.active_transmissions) < base_station.num_rbs:
        # If an RB is free, use it
        rb = next(rb for rb in base_station.resource_blocks 
                  if id(rb) not in base_station.active_transmissions)
        rb.current_SINR = base_station.calculate_SINR(device)
        with rb.resource.request() as req: # No more priority
            yield req
            base_station.active_transmissions[id(rb)] = (device, packet, base_station.env.now)
            data_rate = base_station.channel_model.calculate_data_rate(rb.current_SINR)
            transmission_time = packet.size / (data_rate * rb.subcarriers)
            logger.log(base_station.env.now, device.id, packet.id, "transmission_start", 
                       sinr=rb.current_SINR)
            print(f"Time {base_station.env.now:.3f}: Starting transmission for device {device.id}, packet {packet.id}, SINR: {rb.current_SINR:.2f} dB, data rate: {data_rate/1e6:.2f} Mbps, time: {transmission_time*1000:.2f} ms")
            yield base_station.env.timeout(transmission_time)
            yield base_station.env.process(base_station.release_resource(rb, device, packet))
    else:
       # Use packet.deadline as priority:
        yield base_station.waiting_queue.put((packet.deadline, (device, packet)))


"""Old algorithm: Grok
def proportional_fair(base_station, device, packet):
    # This function implements Proportional Fairness scheduling
    # It balances priority and past throughput for fairness
    logger = get_logger()
    if len(base_station.active_transmissions) < base_station.num_rbs:
        # If an RB is free, use it
        rb = next(rb for rb in base_station.resource_blocks 
                  if id(rb) not in base_station.active_transmissions)
        rb.current_SINR = base_station.calculate_SINR(device)
        with rb.resource.request(priority=packet.priority) as req:
            yield req
            base_station.active_transmissions[id(rb)] = (device, packet, base_station.env.now)
            data_rate = base_station.channel_model.calculate_data_rate(rb.current_SINR)
            transmission_time = packet.size / (data_rate * rb.subcarriers)
            logger.log(base_station.env.now, device.id, packet.id, "transmission_start", 
                       sinr=rb.current_SINR)
            yield base_station.env.timeout(transmission_time)
            base_station.release_resource(rb, device, packet)
    else:
        # Add to the queue; sorting by weight happens in release_resource
        yield base_station.waiting_queue.put((device, packet))
"""
#New algorithm: Gemini
def proportional_fair(base_station, device, packet):
    logger = get_logger()
    if len(base_station.active_transmissions) < base_station.num_rbs:
        rb = next(rb for rb in base_station.resource_blocks
                  if id(rb) not in base_station.active_transmissions)
        rb.current_SINR = base_station.calculate_SINR(device)
        with rb.resource.request() as req: # No more priority
            yield req
            base_station.active_transmissions[id(rb)] = (device, packet, base_station.env.now)
            data_rate = base_station.channel_model.calculate_data_rate(rb.current_SINR)
            transmission_time = packet.size / (data_rate * rb.subcarriers)
            logger.log(base_station.env.now, device.id, packet.id, "transmission_start",
                       sinr=rb.current_SINR)
            print(f"Time {base_station.env.now:.3f}: Starting transmission for device {device.id}, packet {packet.id}, SINR: {rb.current_SINR:.2f} dB, data rate: {data_rate/1e6:.2f} Mbps, time: {transmission_time*1000:.2f} ms")
            yield base_station.env.timeout(transmission_time)
            yield base_station.env.process(base_station.release_resource(rb, device, packet))
    else:
        # Calculate the weight for proportional fairness.
        if device.throughput_history:
            avg_throughput = np.mean([th[1] for th in device.throughput_history])
        else:
            avg_throughput = 0  # Handle devices with no throughput history.

        # Add a small constant to avoid division by zero.
        weight = packet.priority / (avg_throughput + 1e-9)

        # Inverted weight for PriorityStore:
        yield base_station.waiting_queue.put((1/weight, (device, packet)))


def hybrid_edf_preemptive(base_station, device, packet):
    # This function implements Hybrid EDF-Preemptive scheduling
    # It combines EDF with preemption based on deadlines
    logger = get_logger()
    if len(base_station.active_transmissions) < base_station.num_rbs:
        # If an RB is free, use it
        rb = next(rb for rb in base_station.resource_blocks 
                  if id(rb) not in base_station.active_transmissions)
        rb.current_SINR = base_station.calculate_SINR(device)
        with rb.resource.request() as req: # No more priority
            yield req
            base_station.active_transmissions[id(rb)] = (device, packet, base_station.env.now)
            data_rate = base_station.channel_model.calculate_data_rate(rb.current_SINR)
            transmission_time = packet.size / (data_rate * rb.subcarriers)
            logger.log(base_station.env.now, device.id, packet.id, "transmission_start", 
                       sinr=rb.current_SINR)
            print(f"Time {base_station.env.now:.3f}: Starting transmission for device {device.id}, packet {packet.id}, SINR: {rb.current_SINR:.2f} dB, data rate: {data_rate/1e6:.2f} Mbps, time: {transmission_time*1000:.2f} ms")
            yield base_station.env.timeout(transmission_time)
            yield base_station.env.process(base_station.release_resource(rb, device, packet))
    else:
        # Check for preemption based on deadlines
        remaining_times = {}
        for rb in base_station.resource_blocks: # Iterate through resource blocks directly
            if id(rb) in base_station.active_transmissions:
                dev, pkt, start_time = base_station.active_transmissions[id(rb)]
                data_rate = base_station.channel_model.calculate_data_rate(rb.current_SINR)
                total_time = pkt.size / (data_rate * rb.subcarriers)
                elapsed = base_station.env.now - start_time
                remaining_times[rb.id] = total_time - elapsed  # Use rb.id for dictionary key
        # Time until this packet's deadline
        time_to_deadline = packet.deadline - base_station.env.now
        # Find the longest remaining time among active transmissions
        if remaining_times:
            max_remaining = max(remaining_times.values())
            if time_to_deadline < max_remaining:
                # Find RB with the largest remaining time
                rb_to_preempt_id = max(remaining_times, key=remaining_times.get)

                # Find the actual ResourceBlock object using rb_to_preempt_id
                rb_to_preempt = None
                for rb in base_station.resource_blocks:
                    if rb.id == rb_to_preempt_id:
                        rb_to_preempt = rb
                        break
                preempted_device, preempted_packet, _ = base_station.active_transmissions[id(rb_to_preempt)]
                del base_station.active_transmissions[id(rb_to_preempt)]  # Use id(rb_to_preempt)
                # Add a 0.1 ms penalty (simplified)
                yield base_station.env.timeout(0.1)
                # Use packet.deadline for preempted packet:
                yield base_station.waiting_queue.put((preempted_packet.deadline, (preempted_device, preempted_packet)))
                # Use the freed RB
                rb = rb_to_preempt # Use the actual RB object
                rb.current_SINR = base_station.calculate_SINR(device)
                with rb.resource.request() as req: # No more priority
                    yield req
                    base_station.active_transmissions[id(rb)] = (device, packet, base_station.env.now)
                    data_rate = base_station.channel_model.calculate_data_rate(rb.current_SINR)
                    transmission_time = packet.size / (data_rate * rb.subcarriers)
                    logger.log(base_station.env.now, device.id, packet.id, "transmission_start", 
                               sinr=rb.current_SINR)
                    print(f"Time {base_station.env.now:.3f}: Starting transmission for device {device.id}, packet {packet.id}, SINR: {rb.current_SINR:.2f} dB, data rate: {data_rate/1e6:.2f} Mbps, time: {transmission_time*1000:.2f} ms")
                    yield base_station.env.timeout(transmission_time)
                    yield base_station.env.process(base_station.release_resource(rb, device, packet))
            else:
                # Use packet.deadline for the new packet:
                yield base_station.waiting_queue.put((packet.deadline, (device, packet)))
        else:
             # Use packet.deadline if no active transmissions:
             yield base_station.waiting_queue.put((packet.deadline, (device, packet)))

def fiveg_fixed_priority(base_station, device, packet):
    # This function implements a 5G Fixed-Priority scheduler (baseline)
    # It uses a simple priority queue without preemption
    logger = get_logger()
    if len(base_station.active_transmissions) < base_station.num_rbs:
        # If an RB is free, use it
        rb = next(rb for rb in base_station.resource_blocks 
                  if id(rb) not in base_station.active_transmissions)
        rb.current_SINR = base_station.calculate_SINR(device)
        with rb.resource.request() as req: # No more priority
            yield req
            base_station.active_transmissions[id(rb)] = (device, packet, base_station.env.now)
            data_rate = base_station.channel_model.calculate_data_rate(rb.current_SINR)
            transmission_time = packet.size / (data_rate * rb.subcarriers)
            logger.log(base_station.env.now, device.id, packet.id, "transmission_start", 
                       sinr=rb.current_SINR)
            print(f"Time {base_station.env.now:.3f}: Starting transmission for device {device.id}, packet {packet.id}, SINR: {rb.current_SINR:.2f} dB, data rate: {data_rate/1e6:.2f} Mbps, time: {transmission_time*1000:.2f} ms")
            yield base_station.env.timeout(transmission_time)
            yield base_station.env.process(base_station.release_resource(rb, device, packet))
    else:
        # Use packet.priority:
        yield base_station.waiting_queue.put((packet.priority, (device, packet)))