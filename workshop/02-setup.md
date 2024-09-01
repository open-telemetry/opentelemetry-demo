# Exercise 2: Local setup

In this section, we will set up the environment for the workshop. We will use Docker and Docker Compose to run the services required for the workshop.

## Prerequisites

Make sure you have the following tools installed on your machine:

* [Git](https://git-scm.com/)
* [Docker](https://www.docker.com/)
* [Docker Compose](https://docs.docker.com/compose/)

## Clone the repository

Clone the repository to your local machine:

```bash
git clone git@github.com:nais/opentelemetry-workshop.git
```

## Pull the Docker images

Pull the Docker images required for the workshop:

```bash
docker-compose pull
```

!!! note
    The images are quite large, so it might take a while to download them :coffee:


## Next steps

Now that you have the repository cloned and the Docker images pulled, you are ready to start the workshop. In the next section, we will cover the basics of instrumentation with OpenTelemetry.

Continue to [Exercise 3: Instrumentation with JAVA](./03-instrumentation.md)