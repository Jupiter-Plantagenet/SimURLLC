# entities.py
# This file defines all the simulation entities (classes) for SimURLLC.
# Part 1 covers the BaseStation class, which manages resource blocks and scheduling.

import simpy  # SimPy library for discrete-event simulation
import random  # For random interference timing and values
import math    # For logarithmic calculations in SINR
from utils import get_logger  # Import our logger from utils.py
# Import all scheduling functions from scheduling.py
from scheduling import (preemptive_priority, non_preemptive_priority, round_robin,
                       earliest_deadline_first, proportional_fair, hybrid_edf_preemptive,
                       fiveg_fixed_priority)


class BaseStation:
    # The BaseStation manages resource blocks, schedules packets, and simulates interference
    def __init__(self, env, num_rbs, scheduling_policy):
        # Constructor to set up the BaseStation with initial attributes
        self.env = env  # Store the SimPy environment to manage time and events
        self.num_rbs = num_rbs  # Number of resource blocks (e.g., 3 from config)
        # Create a list of ResourceBlock objects, one for each resource block
        self.resource_blocks = [ResourceBlock(env, i, slot_duration=0.125, subcarriers=12) 
                               for i in range(num_rbs)]
        self.scheduling_policy = scheduling_policy  # Which scheduling algorithm to use (e.g., "non-preemptive")
        # Create a SimPy Store to act as a queue for devices waiting for resources
        self.waiting_queue = simpy.Store(env)
        # Dictionary to track which resource blocks are in use: {RB ID: (device, packet, start_time)}
        self.active_transmissions = {}
        # Create a ChannelModel to handle SINR and data rate calculations
        self.channel_model = ChannelModel(env, path_loss_exponent=3.5, noise_power=-174)
        # Start the interference process to simulate random channel disruptions
        self.env.process(self.interference_process(interference_rate=1))

    def request_resource(self, device, packet):
        # This method handles a device’s request to use a resource block for a packet
        logger = get_logger()  # Get the logger to record events
        # Log that a request is happening with the current time, device ID, and packet ID
        logger.log(self.env.now, device.id, packet.id, "request")
        # Print a message to show what’s happening (useful for debugging)
        print(f"Time {self.env.now:.3f}: Device {device.id} requests packet {packet.id}")

        # Choose which scheduling algorithm to use based on the policy
        if self.scheduling_policy == "preemptive":
            # Call the preemptive priority scheduler
            yield self.env.process(preemptive_priority(self, device, packet))
        elif self.scheduling_policy == "non-preemptive":
            # Call the non-preemptive priority scheduler
            yield self.env.process(non_preemptive_priority(self, device, packet))
        elif self.scheduling_policy == "round-robin":
            # Call the round-robin scheduler
            yield self.env.process(round_robin(self, device, packet))
        elif self.scheduling_policy == "edf":
            # Call the earliest deadline first scheduler
            yield self.env.process(earliest_deadline_first(self, device, packet))
        elif self.scheduling_policy == "proportional-fair":
            # Call the proportional fairness scheduler
            yield self.env.process(proportional_fair(self, device, packet))
        elif self.scheduling_policy == "hybrid-edf-preemptive":
            # Call the hybrid EDF-preemptive scheduler
            yield self.env.process(hybrid_edf_preemptive(self, device, packet))
        elif self.scheduling_policy == "5g-fixed":
            # Call the 5G fixed-priority scheduler
            yield self.env.process(fiveg_fixed_priority(self, device, packet))
        else:
            # If the policy isn’t recognized, print an error and stop
            print(f"Error: Unknown scheduling policy '{self.scheduling_policy}'")
            raise ValueError("Invalid scheduling policy")

    def release_resource(self, resource_block, device, packet):
        # This method frees up a resource block after a packet is transmitted
        logger = get_logger()  # Get the logger to record the event
        # Get the start time of this transmission from the active_transmissions dictionary
        start_time = self.active_transmissions[id(resource_block)][2]
        # Remove this resource block from active transmissions since it’s now free
        del self.active_transmissions[id(resource_block)]
        # Calculate how long the packet took to transmit (latency)
        latency = self.env.now - packet.creation_time
        # Tell the device to record its metrics (e.g., packets sent, latency)
        device.record_metrics(packet, latency, success=True)
        # Log that the transmission ended with all relevant metrics
        logger.log(self.env.now, device.id, packet.id, "transmission_end", 
                   latency=latency, aoi=device.aoi, sinr=resource_block.current_SINR)
        # Print a message to confirm the resource block is released
        print(f"Time {self.env.now:.3f}: Device {device.id} released RB {resource_block.id}, latency {latency:.6f}")
        # Check if there are devices waiting in the queue
        if self.waiting_queue.items:
            # Get the next device and packet from the queue (order depends on scheduler)
            next_device, next_packet = yield self.waiting_queue.get()
            # Start a new process to handle this next request
            self.env.process(self.request_resource(next_device, next_packet))

    def run(self, sim_duration):
        # This method keeps the BaseStation active for the entire simulation
        # Wait for the full simulation duration (e.g., 10 seconds)
        yield self.env.timeout(sim_duration)

    def calculate_SINR(self, device):
        # This method calculates the Signal-to-Interference-plus-Noise Ratio (SINR) in dB
        distance = device.location  # Distance from device to base station in meters
        # Use an urban path loss model (3GPP TR 38.901): PL = 35.3 + 37.6 * log10(d)
        path_loss = 35.3 + 37.6 * math.log10(distance)
        # Calculate signal power: transmission power minus path loss
        signal_power_db = self.channel_model.transmission_power - path_loss
        # Get interference power from the channel model (e.g., -90 to -80 dBm)
        interference_db = self.channel_model.interference_level
        # Calculate noise power: -174 dBm/Hz plus 10 * log10(100 MHz bandwidth)
        noise_db = self.channel_model.noise_power + 10 * math.log10(100e6)  # ≈ -94 dBm
        # Combine interference and noise in linear scale, then convert back to dB
        total_noise_linear = 10 ** (interference_db / 10) + 10 ** (noise_db / 10)
        total_noise_db = 10 * math.log10(total_noise_linear)
        # SINR in dB is signal power minus total noise power
        sinr_db = signal_power_db - total_noise_db
        # Ensure SINR isn’t too low; set a minimum of 5 dB for a usable signal
        sinr_db = max(sinr_db, 5.0)
        # Print for debugging to check signal, noise, and SINR values
        print(f"Signal: {signal_power_db:.2f} dB, Noise+Int: {total_noise_db:.2f} dB, SINR: {sinr_db:.2f} dB")
        return sinr_db

    def interference_process(self, interference_rate):
        # This method simulates random interference bursts affecting the channel
        logger = get_logger()  # Get the logger to record interference events
        while True:  # Run forever during the simulation
            # Wait for a random time based on an exponential distribution (e.g., 1 burst/s)
            yield self.env.timeout(random.expovariate(interference_rate))
            # Set a new interference level between -90 and -80 dBm (mild interference)
            self.channel_model.interference_level = random.uniform(-90, -80)
            # Update SINR for all active resource blocks
            for rb in self.resource_blocks:
                # Check if this resource block is currently in use
                if id(rb) in self.active_transmissions:
                    # Get the device using this resource block
                    device = self.active_transmissions[id(rb)][0]
                    # Recalculate SINR based on the new interference
                    rb.current_SINR = self.calculate_SINR(device)
                    # Log the interference event with the new SINR
                    logger.log(self.env.now, -1, -1, "interference", sinr=rb.current_SINR)
            # Print a message to show the interference happened
            print(f"Time {self.env.now:.3f}: Interference burst, level {self.channel_model.interference_level:.2f} dBm")


class URLLCDevice:
    # This class represents a device that generates and sends packets in the simulation
    def __init__(self, env, id, location, arrival_rate, packet_size, base_station, priority, max_latency):
        # Constructor to set up the device with initial attributes
        self.env = env  # Store the SimPy environment to manage time and events
        self.id = id  # Unique ID for this device (e.g., 0, 1, 2...)
        self.location = location  # Distance from base station in meters (e.g., 10-100)
        self.arrival_rate = arrival_rate  # How often packets arrive (packets/s, e.g., 10)
        self.packet_size = packet_size  # Size of each packet in bits (e.g., 102400)
        self.base_station = base_station  # Reference to the BaseStation handling this device
        self.priority = priority  # Priority level (e.g., 1, 2, 3 where 1 is highest)
        self.max_latency = max_latency  # Max allowed latency in seconds (e.g., 0.001 for 1 ms)
        self.packets_sent = 0  # Count of successfully transmitted packets
        self.packets_dropped = 0  # Count of packets dropped (e.g., due to deadline misses)
        self.latencies = []  # List to store latency of each sent packet
        self.aoi = 0.0  # Age of Information: time since last update’s creation
        self.throughput_history = []  # List of (time, throughput) tuples for this device
        self.last_update_time = 0.0  # Time when the last packet’s data was fresh (creation time)
        # Start the packet generation process immediately when the device is created
        self.env.process(self.generate_packets())

    def generate_packets(self):
        # This method generates packets randomly over time using a Poisson process
        logger = get_logger()  # Get the logger to record packet generation
        while True:  # Keep generating packets forever during the simulation
            # Wait for a random time based on the arrival rate (e.g., ~0.1 s for rate=10)
            yield self.env.timeout(random.expovariate(self.arrival_rate))
            # Create a new packet with current attributes
            packet = Packet(self.env.now, self, self.packet_size, self.priority, self.max_latency)
            # Assign a unique ID to the packet (random number between 1000 and 9999)
            packet.id = random.randint(1000, 9999)
            # Log that we generated a packet
            logger.log(self.env.now, self.id, packet.id, "generated")
            # Print a message to show the packet was created
            print(f"Time {self.env.now:.3f}: Generating packet {packet.id} for device {self.id}")
            # Start a process to send this packet to the base station
            self.env.process(self.send_packet(packet))

    def send_packet(self, packet):
        # This method tries to send a packet to the base station and handles deadlines
        logger = get_logger()  # Get the logger to record events
        # Create an event to track when the packet’s deadline is reached
        deadline_event = self.env.event()
        # Start a process to check if the deadline is missed
        self.env.process(self.deadline_check(packet, deadline_event))
        # Start the transmission process by requesting a resource from the base station
        transmission = self.env.process(self.base_station.request_resource(self, packet))
        # Wait for either the transmission to finish or the deadline to hit
        result = yield transmission | deadline_event
        # Check if the deadline was reached before the transmission completed
        if deadline_event in result and transmission not in result:
            # Calculate latency as the time from creation to now (even if dropped)
            latency = self.env.now - packet.creation_time
            # Record that this packet was dropped due to deadline miss
            self.record_metrics(packet, latency, success=False)
            # Log the drop event
            logger.log(self.env.now, self.id, packet.id, "dropped_deadline", latency=latency)
            # Print a message to show the packet was dropped
            print(f"Time {self.env.now:.3f}: Device {self.id} dropped packet {packet.id} (deadline missed)")
        # Print the result of sending (for debugging, shows which event triggered)
        print(f"Time {self.env.now:.3f}: Sending packet {packet.id}, result: {result}")

    def record_metrics(self, packet, latency, success):
        # This method updates the device’s performance metrics after a packet is sent or dropped
        if success:
            # If the packet was successfully sent:
            self.packets_sent += 1  # Increment the count of sent packets
            self.latencies.append(latency)  # Add this packet’s latency to the list
            # Update the last update time to when this packet was created (its data’s freshness)
            self.last_update_time = packet.creation_time
            # AoI is 0 right after a successful transmission (data is fresh)
            self.aoi = 0.0
            # Calculate throughput for this packet (bits per second) and store it
            throughput = self.packet_size / latency if latency > 0 else 0
            self.throughput_history.append((self.env.now, throughput))
            # Print the recorded metrics for debugging
            print(f"Time {self.env.now:.3f}: Recorded latency {latency:.6f}, AoI {self.aoi:.6f}")
        else:
            # If the packet was dropped (e.g., deadline missed):
            self.packets_dropped += 1  # Increment the dropped packet count
        # Update AoI as the time since the last successful packet’s creation
        # This captures staleness for queued packets too
        self.aoi = max(self.aoi, self.env.now - self.last_update_time)

    def deadline_check(self, packet, deadline_event):
        # This method triggers an event if the packet misses its deadline
        # Wait until the deadline (or 0 if already passed) to avoid negative timeouts
        yield self.env.timeout(max(0, packet.deadline - self.env.now))
        # Trigger the deadline event to signal that the packet is late
        deadline_event.succeed()


class ResourceBlock:
    # This class represents a single resource block (like a channel) at the base station
    def __init__(self, env, id, slot_duration, subcarriers):
        # Constructor to set up the resource block
        # Create a PriorityResource with capacity 1 (only one device can use it at a time)
        self.resource = simpy.PriorityResource(env, capacity=1)
        self.id = id  # Unique ID for this resource block (e.g., 0, 1, 2)
        self.slot_duration = slot_duration  # Time per slot in ms (e.g., 0.125 ms)
        self.subcarriers = subcarriers  # Number of subcarriers (e.g., 12)
        self.current_SINR = 10.0  # Initial Signal-to-Interference-plus-Noise Ratio in dB


class Packet:
    # This class represents a packet sent by a device
    def __init__(self, creation_time, source, size, priority, max_latency):
        # Constructor to set up the packet
        self.id = None  # Packet ID will be set later when generated (e.g., 1234)
        self.creation_time = creation_time  # When the packet was created (in sim time)
        self.source = source  # The URLLCDevice that made this packet
        self.size = size  # Size in bits (e.g., 102400 bits)
        self.priority = priority  # Priority level (e.g., 1, 2, 3)
        # Deadline is when the packet must be sent by (creation time + max latency)
        self.deadline = creation_time + max_latency


class ChannelModel:
    # This class calculates how good the signal is (SINR) and the resulting data rate
    def __init__(self, env, path_loss_exponent, noise_power):
        # Constructor to set up the channel model
        self.env = env  # Store the SimPy environment
        self.path_loss_exponent = path_loss_exponent  # How fast signal weakens (e.g., 3.5)
        self.noise_power = noise_power  # Background noise in dBm/Hz (e.g., -174)
        self.interference_level = -90.0  # Initial interference power in dBm (quiet)
        self.transmission_power = 23  # Power devices use to send signals in dBm

    def calculate_data_rate(self, SINR):
        # This method turns SINR (in dB) into a data rate (bits per second)
        bandwidth = 100e6  # Bandwidth in Hz (100 MHz, typical for 6G)
        # Convert SINR from dB to linear scale (e.g., 10 dB becomes 10)
        sinr_linear = 10 ** (SINR / 10)
        # If SINR is too low (or negative), use a minimum data rate
        if sinr_linear <= 0:
            return 1000000  # 1 Mbps as a fallback
        # Calculate data rate using Shannon’s formula: bandwidth * log2(1 + SINR)
        data_rate = bandwidth * math.log2(1 + sinr_linear)
        # Cap the data rate at 20 Mbps (from config) to keep it realistic
        return min(data_rate, 20000000)