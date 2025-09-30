# Contributing to OpenTelemetry Demo Webstore

Welcome to the OpenTelemetry Demo repository! We appreciate your interest in
contributing. Whether you're fixing a bug, improving documentation, or adding a
new feature, we value your contribution.

Before getting started, please review the
[OpenTelemetry Contributor Guide](https://github.com/open-telemetry/community/blob/main/guides/contributor/README.md)
for details on code attribution and best practices.

## Getting Started

### Join a SIG Call

We meet every other Wednesday at 8:00 PT. The schedule may change based on
contributors' availability. Check the [OpenTelemetry Community Calendar](https://github.com/open-telemetry/community?tab=readme-ov-file#special-interest-groups)
for specific dates and Zoom links.

See the
[public meeting notes](https://docs.google.com/document/d/16f-JOjKzLgWxULRxY8TmpM_FjlI1sthvKurnqFz9x98/edit)
for a summary description of past meetings.
For edit access, ask in our
[Slack channel](https://cloud-native.slack.com/archives/C03B4CWV4DA).

### Sign the Contributor License Agreement (CLA)

Before contributing, sign the [CLA](https://identity.linuxfoundation.org/projects/cncf)

### Find a Mentor (Buddy System)

New to OpenTelemetry? We encourage you to find a mentor who can guide you
through your first contribution.

1. Create your [CNCF Slack account](https://slack.cncf.io/) and join the
   [otel-community-demo](https://app.slack.com/client/T08PSQ7BQ/C03B4CWV4DA)
   channel.
2. Post in the room with an introduction to yourself, what area you are
   interested in (check issues marked with [help
   wanted](https://github.com/open-telemetry/opentelemetry-demo/labels/help%20wanted)),
   and say you are looking for a buddy. We will match you with someone who has
   experience in that area.

Your OpenTelemetry buddy is your resource to talk to directly on all aspects of
contributing to OpenTelemetry: providing context, reviewing PRs, and helping
those get merged. Buddies will not be available 24/7, but is committed to
responding during their normal contribution hours.

## Setting Up Your Development Environment

### Prerequisites

Ensure you have the following installed:

- [Git](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git)
- [Make](https://www.gnu.org/software/make/)
- [Docker](https://www.docker.com/get-started/)
- [Docker Compose](https://docs.docker.com/compose/install/#install-compose) v2.0.0+

### Clone the Repository

```sh
git clone https://github.com/open-telemetry/opentelemetry-demo.git
cd opentelemetry-demo/
```

### Run the Demo

```sh
make start
```

### Verify the Webstore & Telemetry

Once the images are built and containers are started, visit:

- **Webstore**: [http://localhost:8080/](http://localhost:8080/)
- **Jaeger**: [http://localhost:8080/jaeger/ui/](http://localhost:8080/jaeger/ui/)
- **Grafana**: [http://localhost:8080/grafana/](http://localhost:8080/grafana/)
- **Feature Flags UI**: [http://localhost:8080/feature/](http://localhost:8080/feature/)
- **Load Generator UI**: [http://localhost:8080/loadgen/](http://localhost:8080/loadgen/)

## Troubleshooting Common Issues

### Docker Not Running

**Error:** `Error response from daemon: Docker daemon is not running.`

**Solution:**

- **Windows/macOS**: Open Docker Desktop and ensure it's running.
- **Linux**: Check Docker status:

```sh
systemctl status docker
```

If inactive, start it:

```sh
sudo systemctl start docker
  ```

### Gradle Issues (Windows)

If you encounter Gradle issues, run:

```sh
cd src/ad/
./gradlew installDist
./gradlew wrapper --gradle-version 7.4.2
```

### Docker build cache issues

While developing, you may encounter issues with Docker build cache. To clear the
cache:

```sh
docker system prune -a
```

Warning: This removes all unused Docker data, including images, containers,
volumes, and networks. Use with caution.

### Debugging Tips

- Use `docker ps` to check running containers.
- View logs for services:

```sh
docker logs <container_id>
```

- Restart containers if needed:

```sh
docker-compose restart
```

### Review the Documentation

The Demo team is committed to keeping the demo up to date. That means the
documentation as well as the code. When making changes to any service or feature
remember to find the related docs and update those as well. Most (but not all)
documentation can be found on the OTel website under [Demo docs][docs].

### Running the React Native example

If you are interested in running the React Native example app in this repo
please review [these instructions](src/react-native-app/README.md).

## Create Your First Pull Request

### How to Send Pull Requests

Everyone is welcome to contribute code to `opentelemetry-demo` via
GitHub pull requests (PRs).

To create a new PR, fork the project in GitHub and clone the upstream repo:

> [!NOTE]
> Please fork to a personal GitHub account rather than a corporate/enterprise
> one so maintainers can push commits to your branch.
> **Pull requests from protected forks will not be accepted.**

```sh
git clone https://github.com/open-telemetry/opentelemetry-demo.git
```

Navigate to the repo root:

```sh
cd opentelemetry-demo
```

Add your fork as an origin:

```sh
git remote add fork https://github.com/YOUR_GITHUB_USERNAME/opentelemetry-demo.git
```

Check out a new branch, make modifications and push the branch to your fork:

```sh
$ git checkout -b feature
# change files
# Test your changes locally.
$ docker compose up -d --build
# Go to Webstore, Jaeger or docker container logs etc. as appropriate to make sure your changes are working correctly.
$ git add my/changed/files
$ git commit -m "short description of the change"
$ git push fork feature
```

Open a pull request against the main `opentelemetry-demo` repo.

### How to Receive Comments

- If the PR is not ready for review, please mark it as
  [`draft`](https://github.blog/2019-02-14-introducing-draft-pull-requests/).
- Make sure CLA is signed and all required CI checks are clear.
- Submit small, focused PRs addressing a single
  concern/issue.
- Make sure the PR title reflects the contribution.
- Write a summary that helps understand the change.
- Include usage examples in the summary, where applicable.
- Include benchmarks (before/after) in the summary, for contributions that are
  performance enhancements.

### How to Get PRs Merged

A PR is considered to be **ready to merge** when:

- It has received approval from
  [Approvers](https://github.com/open-telemetry/community/blob/main/guides/contributor/membership.md#approver)
  /
  [Maintainers](https://github.com/open-telemetry/community/blob/main/guides/contributor/membership.md#maintainer).
- Major feedbacks are resolved.
- It has been open for review for at least one working day. This gives people
  reasonable time to review.
- The [documentation][docs] and [Changelog](./CHANGELOG.md) have been updated
  to reflect the new changes.
- Trivial changes (typo, cosmetic, doc, etc.) don't have to wait for one day.

Any Maintainer can merge the PR once it is **ready to merge**. Note, that some
PRs may not be merged immediately if the repo is in the process of a release and
the maintainers decided to defer the PR to the next release train.

If a PR has been stuck (e.g. there are lots of debates and people couldn't agree
on each other), the owner should try to get people aligned by:

- Consolidating the perspectives and putting a summary in the PR. It is
  recommended to add a link into the PR description, which points to a comment
  with a summary in the PR conversation.
- Tagging subdomain experts (by looking at the change history) in the PR asking
  for suggestion.
- Reaching out to more people on the [CNCF OpenTelemetry Community Demo Slack
  channel](https://app.slack.com/client/T08PSQ7BQ/C03B4CWV4DA).
- Stepping back to see if it makes sense to narrow down the scope of the PR or
  split it up.
- If none of the above worked and the PR has been stuck for more than 2 weeks,
  the owner should bring it to the OpenTelemetry Community Demo SIG
  [meeting](README.md#contributing).

## Multi-platform Builds

Creating multi-platform builds requires docker buildx to be installed. This
is part of Docker Desktop for macOS, or can be installed using
`apt install docker-buildx` on Ubuntu.

To build and load the multi-platform images locally you will need to configure
docker to use `containerd`. This can be done in Docker Desktop settings on MacOS
or Windows. Please follow
[these instructions](https://docs.docker.com/engine/storage/containerd/#enable-containerd-image-store-on-docker-engine)
to configure Docker Engine on Linux/Ubuntu.

You will need a multi-platform capable builder with a limiter set on parallelism
to avoid errors while building the images. It is recommended to limit the
parallelism to 4. This can be done by specifying a configuration file when
creating the builder. The `buildkitd.toml` file in this repository can be used
as the builder configuration file.

To create a multi-platform builder with a parallelism limit of 4, use the
following command:

```shell
make create-multiplatform-builder
```

A builder will be created and set as the active builder. You can check the
builder status with `docker buildx inspect`. To build multi-platform images for
linux/amd64 and linux/arm64, use the following command:

```shell
make build-multiplatform
```

To build and push multi-platform images to a registry, ensure to set
`IMAGE_NAME` to the name of the registry and image repository to use in the
`.env.override` file and run:

```shell
make build-multiplatform-and-push
```

## Making a new release

Maintainers can create a new release when desired by following these steps.

1. Create a Pull Request that updates the `IMAGE_VERSION` environment variable
   in `.env` to the _new_ version number based on the format `x.x.x` and merge
   it.
2. [Create a new
   release](https://github.com/open-telemetry/opentelemetry-demo/releases/new),
   creating a new tag for the _new_ version number based on main. Automatically
   generate release notes. Prepend a summary of the major changes to the release
   notes.
3. After images for the new release are built and published, create a new Pull
   Request that updates the `CHANGELOG.md` with the new version leaving the
   `Unreleased` section for the next release. Merge the Pull Request.
4. Create a new Pull Request to update the deployment of the demo in the
   [OpenTelemetry Helm
   Charts](https://github.com/open-telemetry/opentelemetry-helm-charts) repo.
   Merge the Pull Request.
5. After the Helm chart is released, create a new Pull Request which updates the
   Demo's Kubernetes manifest by running `make generate-kubernetes-manifests`.
   Merge the Pull Request.

[docs]: https://opentelemetry.io/docs/demo/

By following this guide, you'll have a smoother onboarding experience as a
contributor. Happy coding!
