#!/bin/bash
# Build and run the math_server Docker container

# Build the Docker image
echo "Building math_server Docker image..."
docker build -t math_server .

# Run the container
echo "Running math_server container..."
docker run -d --name math_server -p 8002:8002 math_server

echo "Math server should now be running on port 8002"
echo "Check container status with: docker ps"
echo "View logs with: docker logs math_server"
