# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    gfortran \
    libblas-dev \
    liblapack-dev \
    # Additional dependencies for cvxopt
    && apt-get install -y libgmp-dev \
    && rm -rf /var/lib/apt/lists/* \
    && pip install cvxopt


# Set the working directory to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
ADD . /app

# Install any needed packages specified in requirements.in
RUN pip install --no-cache-dir -r requirements.in

# Expose the port the app runs on
EXPOSE 5003

# Command to run the app using pserve
CMD ["pserve", "development.ini"]
