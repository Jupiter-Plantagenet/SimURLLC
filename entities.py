# entities.py
import simpy
import random
import math
from utils import get_logger

class BaseStation:
    def __init__(self, env, num_rbs, scheduling_policy, devices):
        self.env = env
        self.num_rbs = num_rbs
        self.resource_blocks = [ResourceBlock(env, i, 0.125, 12) for i in range(num_rbs)]
        self.scheduling_policy = scheduling_policy
        self.waiting_queue = simpy.PriorityStore(env)
        self.active_transmissions = {}  # {rb_id: (device, packet, start_time, rb_object)}
        self.channel_model = ChannelModel(env, 3.5, -174)
        self.next_device_index = 0
        self.devices = devices
        self.env.process(self.interference_process(interference_rate=1))

    def request_resource(self, device, packet):
        # Import scheduling functions here to avoid circular imports
        from scheduling import (preemptive_priority, non_preemptive_priority, 
                              round_robin, earliest_deadline_first, 
                              fiveg_fixed_priority, hybrid_edf_preemptive)
        
        # Dispatch to appropriate scheduling algorithm
        scheduling_map = {
            'preemptive': preemptive_priority,
            'non-preemptive': non_preemptive_priority,
            'round-robin': round_robin,
            'edf': earliest_deadline_first,
            'fiveg-fixed': fiveg_fixed_priority,
            'hybrid-edf': hybrid_edf_preemptive
        }
        
        scheduler = scheduling_map.get(self.scheduling_policy)
        if scheduler:
            return self.env.process(scheduler(self, device, packet))
        else:
            raise ValueError(f"Unknown scheduling policy: {self.scheduling_policy}")

    def release_resource(self, resource_block, device, packet):
        # Remove from active transmissions
        if id(resource_block) in self.active_transmissions:
            start_time = self.active_transmissions[id(resource_block)][2]
            latency = self.env.now - packet.creation_time
            success = latency <= device.max_latency
            
            # Record metrics
            device.record_metrics(packet, latency, success)
            
            # Log transmission end
            logger = get_logger()
            logger.log(
                time=self.env.now,
                device_id=device.id,
                packet_id=packet.id,
                event="transmission_end",
                latency=latency,
                sinr=resource_block.current_SINR
            )
            
            # Remove from active transmissions
            del self.active_transmissions[id(resource_block)]
            
            # Check waiting queue and schedule next transmission
            if len(self.waiting_queue.items) > 0:
                if self.scheduling_policy == 'round-robin':
                    # Round Robin: Get next device in circular order
                    self.next_device_index = (self.next_device_index + 1) % len(self.devices)
                    next_device = self.devices[self.next_device_index]
                    
                    # Find packet from this device in waiting queue
                    for item in self.waiting_queue.items:
                        if item.source == next_device:
                            next_packet = item
                            self.env.process(self.request_resource(next_device, next_packet))
                            break
                else:
                    # For other policies, take next packet from priority queue
                    next_packet = self.waiting_queue.items[0]
                    self.env.process(self.request_resource(next_packet.source, next_packet))

    def calculate_SINR(self, device):
        distance = device.location
        path_loss = 35.3 + 37.6 * math.log10(distance)
        signal_power_db = self.channel_model.transmission_power - path_loss
        interference_db = self.channel_model.interference_level
        noise_db = self.channel_model.noise_power + 10 * math.log10(100e6)
        total_noise_linear = 10 ** (interference_db / 10) + 10 ** (noise_db / 10)
        total_noise_db = 10 * math.log10(total_noise_linear)
        sinr_db = signal_power_db - total_noise_db
        return max(sinr_db, 5.0)

    def interference_process(self, interference_rate):
        while True:
            yield self.env.timeout(random.expovariate(interference_rate))
            self.channel_model.interference_level = random.uniform(-70, -60)
            
            # Update SINR for all active transmissions
            for rb in self.resource_blocks:
                if id(rb) in self.active_transmissions:
                    device = self.active_transmissions[id(rb)][0]
                    rb.current_SINR = self.calculate_SINR(device)
                    
            yield self.env.timeout(random.uniform(0.1, 0.5))
            self.channel_model.interference_level = -90

class URLLCDevice:
    def __init__(self, env, id, location, arrival_rate, packet_size, base_station, priority, max_latency):
        self.env = env
        self.id = id
        self.location = location
        self.arrival_rate = arrival_rate
        self.packet_size = packet_size
        self.base_station = base_station
        self.priority = priority
        self.max_latency = max_latency
        self.packets_sent = 0
        self.packets_dropped = 0
        self.latencies = []
        self.aoi = 0.0
        self.last_update_time = 0.0
        self.throughput_history = []
        self.next_packet_id = 0

    def generate_packets(self):
        while True:
            # Wait for next packet arrival
            yield self.env.timeout(random.expovariate(self.arrival_rate))
            
            # Create new packet
            packet = Packet(
                creation_time=self.env.now,
                source=self,
                size=self.packet_size,
                priority=self.priority,
                max_latency=self.max_latency
            )
            packet.id = self.next_packet_id
            self.next_packet_id += 1
            
            # Start packet transmission process
            self.env.process(self.send_packet(packet))

    def send_packet(self, packet):
        # Create deadline event
        deadline_event = self.env.event()
        self.env.process(self.deadline_check(packet, deadline_event))
        
        # Request resource from base station
        transmission_process = self.base_station.request_resource(self, packet)
        
        # Wait for either transmission completion or deadline
        result = yield simpy.events.AnyOf(self.env, [transmission_process, deadline_event])
        
        if deadline_event in result.events:
            # Packet missed deadline
            self.packets_dropped += 1
            logger = get_logger()
            logger.log(
                time=self.env.now,
                device_id=self.id,
                packet_id=packet.id,
                event="packet_dropped",
                latency=self.max_latency
            )

    def record_metrics(self, packet, latency, success):
        current_time = self.env.now
        
        # Update AoI
        self.aoi = current_time - self.last_update_time
        if success:
            self.last_update_time = current_time
        
        # Record latency
        if success:
            self.latencies.append(latency)
            self.packets_sent += 1
        else:
            self.packets_dropped += 1
        
        # Calculate throughput
        if success:
            throughput = packet.size / latency
            self.throughput_history.append(throughput)

    def deadline_check(self, packet, deadline_event):
        yield self.env.timeout(self.max_latency)
        if not deadline_event.triggered:
            deadline_event.succeed()

class ResourceBlock:
    def __init__(self, env, id, slot_duration, subcarriers):
        self.resource = simpy.PriorityResource(env, capacity=1)
        self.id = id
        self.slot_duration = slot_duration
        self.subcarriers = subcarriers
        self.current_SINR = 10.0

class Packet:
    def __init__(self, creation_time, source, size, priority, max_latency):
        self.id = None  # Assigned in generate_packets
        self.creation_time = creation_time
        self.source = source
        self.size = size
        self.priority = priority
        self.deadline = creation_time + max_latency

    def __lt__(self, other):
        if isinstance(other, Packet):
            return self.priority < other.priority
        return NotImplemented

    def __eq__(self, other):
        if isinstance(other, Packet):
            return self.id == other.id and self.source == other.source
        return NotImplemented

class ChannelModel:
    def __init__(self, env, path_loss_exponent, noise_power):
        self.env = env
        self.path_loss_exponent = path_loss_exponent
        self.noise_power = noise_power
        self.interference_level = -90.0
        self.transmission_power = 23

    def calculate_data_rate(self, SINR, subcarriers, slot_duration):
        bandwidth_per_rb = 180000  # 180 kHz per resource block
        sinr_linear = 10 ** (SINR/10)
        return bandwidth_per_rb * subcarriers * math.log2(1 + sinr_linear) / slot_duration 