# Use a lightweight base image
FROM alpine:latest

# Install SQLite
RUN apk --no-cache add sqlite

# Create a directory to store the database
WORKDIR /db

# Copy your SQL script into the container
COPY product/init.sql /docker-entrypoint-initdb.d/

# Command to run when the container starts
CMD ["sh", "-c", "sqlite3 /db/mydatabase.db < /docker-entrypoint-initdb.d/init.sql && tail -f /dev/null"]