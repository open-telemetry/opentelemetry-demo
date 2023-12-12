import psutil
import time
import sys

# Define the amount of memory to, exact duration to reach it and how long to hold
memory_to_add_mb = 750
increase_duration_seconds = 20000
maintain_duration_seconds = 300

# Calculate the amount of memory to consume in each iteration
memory_to_add_bytes = memory_to_add_mb * (1024 ** 2)
allocation_size = memory_to_add_bytes / increase_duration_seconds

# Create a list to store memory allocations
memory_allocations = []

try:
    # Increase memory usage to the target level
    start_time = time.time()
    count = 0
    while count < increase_duration_seconds:
        memory_allocations.append(bytearray(int(allocation_size)))
        count += 1

        # Calculate the elapsed time
        elapsed_time = time.time() - start_time

        # Calculate the remaining time to sleep
        remaining_time = increase_duration_seconds - elapsed_time
        if remaining_time > 0:
            # Sleep for a short interval
            sleep_interval = min(1, remaining_time)
            time.sleep(sleep_interval)
        else:
            break

        # Get the total memory added in each iteration
        total_memory_added = count * allocation_size
        print(f"Added {total_memory_added / (1024 ** 3):.2f} GB")

    print(f"Added {memory_to_add_gb} GB of memory in {elapsed_time:.2f} seconds.")

except KeyboardInterrupt:
    print("Memory consumption interrupted by user.")

finally:
    # Maintain memory usage for the specified duration
    maintain_duration_seconds = 300
    time.sleep(maintain_duration_seconds)

    # Release the allocated memory
    del memory_allocations
    print("Memory released.")
