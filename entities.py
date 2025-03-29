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
        self.waiting_queue = simpy.Store(env)  # Changed from PriorityStore to Store for simplicity
        self.active_transmissions = {}  # {rb_id: (device, packet, start_time, rb_object)}
        self.channel_model = ChannelModel(env, 3.5, -174)
        self.next_device_index = 0
        self.devices = devices
        self._interference_process = None  # Store process reference but don't include in serialization
        self._interference_process = self.env.process(self.interference_process(interference_rate=1))
        self.preempted_packets = {}  # To track preempted packets
        self.packets_processed = 0
        self.packets_received = 0
        self.debug_logger = get_logger()
    
    def __getstate__(self):
        """Custom state for pickling/serialization"""
        state = self.__dict__.copy()
        # Remove non-serializable attributes
        state.pop('env', None)
        state.pop('waiting_queue', None)
        state.pop('_interference_process', None)
        state.pop('debug_logger', None)
        
        # Remove resource blocks (they contain SimPy resources)
        state.pop('resource_blocks', None)
        
        # Remove references to devices (circular reference)
        state.pop('devices', None)
        
        # Clean active_transmissions (contains references to resource blocks)
        state.pop('active_transmissions', None)
        
        # Keep only serializable data
        return {
            'num_rbs': state['num_rbs'],
            'scheduling_policy': state['scheduling_policy'],
            'next_device_index': state['next_device_index'],
            'packets_processed': state['packets_processed'],
            'packets_received': state['packets_received']
        }

    def request_resource(self, device, packet):
        # Import scheduling functions here to avoid circular imports
        from scheduling import (preemptive_priority, non_preemptive_priority, 
                              round_robin, earliest_deadline_first, 
                              fiveg_fixed_priority, hybrid_edf_preemptive)
        
        # Increment packets received counter
        self.packets_received += 1
        
        # Log packet arrival
        try:
            logger = get_logger()
            logger.log(
                time=self.env.now,
                device_id=device.id,
                packet_id=packet.id if hasattr(packet, 'id') else -1,
                event="packet_arrival",
                latency=0
            )
        except Exception as e:
            print(f"Error logging packet arrival: {str(e)}")
        
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
            # Direct process: schedule the packet immediately if resources available
            for rb in self.resource_blocks:
                if id(rb) not in self.active_transmissions:
                    # Log resource availability
                    try:
                        logger = get_logger()
                        logger.log(
                            time=self.env.now,
                            device_id=device.id,
                            packet_id=packet.id if hasattr(packet, 'id') else -1,
                            event="resource_available",
                            latency=0
                        )
                    except Exception as e:
                        print(f"Error logging resource availability: {str(e)}")
                    
                    return self.env.process(scheduler(self, device, packet))
            
            # No resource block available, add to waiting queue
            try:
                logger = get_logger()
                logger.log(
                    time=self.env.now,
                    device_id=device.id,
                    packet_id=packet.id if hasattr(packet, 'id') else -1,
                    event="queued_for_resource",
                    latency=0
                )
            except Exception as e:
                print(f"Error logging queue event: {str(e)}")
            
            self.waiting_queue.put(packet)
            return self.env.timeout(0)  # Return a dummy process
        else:
            error_msg = f"Unknown scheduling policy: {self.scheduling_policy}"
            try:
                logger = get_logger()
                logger.log(
                    time=self.env.now,
                    device_id=device.id,
                    packet_id=packet.id if hasattr(packet, 'id') else -1,
                    event=f"ERROR: {error_msg}",
                    latency=0
                )
            except Exception as e:
                print(f"Error logging scheduling error: {str(e)}")
            
            raise ValueError(error_msg)

    def release_resource(self, resource_block, device, packet):
        # Remove from active transmissions
        if id(resource_block) in self.active_transmissions:
            start_time = self.active_transmissions[id(resource_block)][2]
            latency = self.env.now - packet.creation_time
            success = latency <= device.max_latency
            
            # Check if SINR is below threshold and drop packet if so
            if success and resource_block.current_SINR < self.channel_model.sinr_threshold:
                success = False
                try:
                    logger = get_logger()
                    logger.log(
                        time=self.env.now,
                        device_id=device.id,
                        packet_id=packet.id if hasattr(packet, 'id') else -1,
                        event="packet_dropped_due_to_low_SINR",
                        latency=latency,
                        sinr=resource_block.current_SINR,
                        sinr_threshold=self.channel_model.sinr_threshold
                    )
                except Exception as e:
                    print(f"Error logging SINR packet drop: {str(e)}")
            
            # Record metrics
            try:
                device.record_metrics(packet, latency, success)
            except Exception as e:
                print(f"Error recording metrics: {str(e)}")
            
            # Log transmission end
            try:
                logger = get_logger()
                logger.log(
                    time=self.env.now,
                    device_id=device.id,
                    packet_id=packet.id if hasattr(packet, 'id') else -1,
                    event="transmission_end",
                    latency=latency,
                    sinr=resource_block.current_SINR
                )
            except Exception as e:
                print(f"Error logging transmission end: {str(e)}")
            
            # Increment packets processed counter
            self.packets_processed += 1
            
            # Remove from active transmissions
            del self.active_transmissions[id(resource_block)]
            
            # Check waiting queue and schedule next transmission
            if self.waiting_queue.items:
                # Get the next packet from the queue
                self.env.process(self.process_next_packet(resource_block))

    def process_next_packet(self, resource_block):
        # Get next packet from queue
        try:
            next_packet = yield self.waiting_queue.get()
            next_device = next_packet.source
            
            # Log packet dequeued
            try:
                logger = get_logger()
                logger.log(
                    time=self.env.now,
                    device_id=next_device.id,
                    packet_id=next_packet.id if hasattr(next_packet, 'id') else -1,
                    event="packet_dequeued",
                    latency=self.env.now - next_packet.creation_time
                )
            except Exception as e:
                print(f"Error logging packet dequeued: {str(e)}")
            
            # Process the packet using the appropriate scheduler
            from scheduling import (preemptive_priority, non_preemptive_priority, 
                                   round_robin, earliest_deadline_first, 
                                   fiveg_fixed_priority, hybrid_edf_preemptive)
            
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
                self.env.process(scheduler(self, next_device, next_packet))
        except Exception as e:
            print(f"Error processing next packet: {str(e)}")

    def calculate_SINR(self, device):
        distance = device.location
        path_loss_exponent = self.channel_model.get_path_loss_exponent(self.env.now)
        path_loss = 35.3 + 37.6 * math.log10(distance)
        signal_power_db = self.channel_model.transmission_power - path_loss
        interference_db = self.channel_model.interference_level
        noise_db = self.channel_model.noise_power + 10 * math.log10(100e6)
        total_noise_linear = 10 ** (interference_db / 10) + 10 ** (noise_db / 10)
        total_noise_db = 10 * math.log10(total_noise_linear)
        sinr_db = signal_power_db - total_noise_db
        return max(sinr_db, 0.1)  # Ensure SINR is positive but allow very low values

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
        
        # Initialize to avoid cold-start
        self.last_update_time = env.now
        
        # Store process reference but don't include in serialization
        self._packet_generator = None
    
    def __getstate__(self):
        """Custom state for pickling/serialization"""
        state = self.__dict__.copy()
        # Remove non-serializable attributes
        state.pop('env', None)
        state.pop('_packet_generator', None)
        
        # Remove reference to base_station (circular reference)
        state.pop('base_station', None)
        
        # Convert numpy arrays to lists if needed
        if hasattr(state['latencies'], 'tolist'):
            state['latencies'] = state['latencies'].tolist()
        if hasattr(state['throughput_history'], 'tolist'):
            state['throughput_history'] = state['throughput_history'].tolist()
        
        return state

    def generate_packets(self):
        """Generate packets according to a Poisson process"""
        # Generate first packet immediately to ensure traffic flow
        yield self.env.timeout(0.001)  # Very small delay to start
        
        # Create first packet
        self.create_and_send_packet()
        
        # Then continue with regular Poisson process
        while True:
            # Calculate interarrival time based on arrival rate (Poisson process)
            interarrival_time = random.expovariate(self.arrival_rate)
            
            # Ensure there's some minimum interarrival time (but not too long)
            interarrival_time = max(0.0005, min(interarrival_time, 0.1))
            
            # Wait for next packet
            yield self.env.timeout(interarrival_time)
            
            # Create and send a new packet
            self.create_and_send_packet()

    def create_and_send_packet(self):
        """Create a new packet and send it"""
        # Create packet
        packet = Packet(
            creation_time=self.env.now,
            source=self,
            size=self.packet_size,
            priority=self.priority,
            max_latency=self.max_latency
        )
        packet.id = self.next_packet_id
        self.next_packet_id += 1
        
        # Log packet creation
        try:
            logger = get_logger()
            logger.log(
                time=self.env.now,
                device_id=self.id,
                packet_id=packet.id,
                event="packet_created",
                latency=0
            )
        except Exception as e:
            print(f"Error logging packet creation: {str(e)}")
        
        # Send packet
        self.env.process(self.send_packet(packet))

    def send_packet(self, packet):
        """Send packet to base station"""
        try:
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
                    event="packet_dropped_deadline",
                    latency=self.max_latency
                )
        except Exception as e:
            # Log any error during packet transmission
            try:
                logger = get_logger()
                logger.log(
                    time=self.env.now,
                    device_id=self.id,
                    packet_id=packet.id if hasattr(packet, 'id') else -1,
                    event=f"ERROR: Send packet failed: {str(e)}",
                    latency=0
                )
            except Exception as log_error:
                print(f"Error logging packet error: {str(log_error)}")
            
            # Print the error for debugging
            print(f"Error sending packet: {str(e)}")

    def record_metrics(self, packet, latency, success):
        """Record metrics for a transmitted packet"""
        current_time = self.env.now
        
        # Update AoI
        self.aoi = current_time - self.last_update_time
        if success:
            self.last_update_time = current_time
        
        # Record latency and update counters
        if success:
            self.latencies.append(latency)
            self.packets_sent += 1
            
            # Log successful packet transmission
            logger = get_logger()
            logger.log(
                time=current_time,
                device_id=self.id,
                packet_id=packet.id,
                event="packet_succeeded",
                latency=latency
            )
        else:
            self.packets_dropped += 1
            
            # Log failed packet transmission
            logger = get_logger()
            logger.log(
                time=current_time,
                device_id=self.id,
                packet_id=packet.id,
                event="packet_failed",
                latency=latency
            )
        
        # Calculate throughput
        if success:
            # Avoid division by zero
            if latency > 0:
                throughput = packet.size / latency
            else:
                throughput = packet.size / 0.0001  # Assume a small but non-zero latency
                
            self.throughput_history.append(throughput)

    def deadline_check(self, packet, deadline_event):
        """Check if a packet has missed its deadline"""
        yield self.env.timeout(self.max_latency)
        if not deadline_event.triggered:
            deadline_event.succeed()

class ResourceBlock:
    def __init__(self, env, id, slot_duration, subcarriers):
        self.resource = simpy.Resource(env, capacity=1)  # Changed from PriorityResource to Resource
        self.id = id
        self.slot_duration = slot_duration
        self.subcarriers = subcarriers
        self.current_SINR = 10.0
        self.env = env
    
    def __getstate__(self):
        """Custom state for pickling/serialization"""
        state = self.__dict__.copy()
        # Remove non-serializable attributes
        state.pop('resource', None)
        state.pop('env', None)
        return state

class Packet:
    def __init__(self, creation_time, source, size, priority, max_latency):
        self.id = None  # Assigned in generate_packets
        self.creation_time = creation_time
        self.source = source
        self.size = size
        self.priority = priority
        self.deadline = creation_time + max_latency
        self.max_latency = max_latency  # Store max_latency directly for easier access
    
    def __getstate__(self):
        """Custom state for pickling/serialization"""
        state = self.__dict__.copy()
        # Remove reference to source (circular reference to device)
        state.pop('source', None)
        return state

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
        self.base_path_loss_exponent = path_loss_exponent
        self.noise_power = noise_power
        self.interference_level = -90.0
        self.transmission_power = 23
        self.time_varying_channel = False
        self.variation_period = 10.0  # Default 10 seconds
        self.variation_amplitude = 0.5  # Default amplitude of variation
        self.sinr_threshold = 5.0  # Default SINR threshold in dB
    
    def __getstate__(self):
        """Custom state for pickling/serialization"""
        state = self.__dict__.copy()
        # Remove non-serializable attributes
        state.pop('env', None)
        return state
    
    def get_path_loss_exponent(self, time):
        """Get the path loss exponent, which may vary with time"""
        if not self.time_varying_channel:
            return self.base_path_loss_exponent
        
        # Apply sinusoidal variation to path loss exponent
        variation = self.variation_amplitude * math.sin(2 * math.pi * time / self.variation_period)
        return self.base_path_loss_exponent + variation

    def calculate_data_rate(self, SINR, subcarriers, slot_duration):
        bandwidth_per_rb = 180000  # 180 kHz per resource block
        sinr_linear = 10 ** (SINR/10)
        return bandwidth_per_rb * subcarriers * math.log2(1 + sinr_linear) / slot_duration 