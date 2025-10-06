# Syncing New Relic OpenTelemetry Demo to Official OpenTelemetry Demo

These instructions allow you to sync this fork with the upstream/official OpenTelemetry Demo, and then create a PR for those changes.
It involves a specific workflow that utilizes `git fetch` and `git merge` (or `git rebase`), while ensuring the updates are applied to a dedicated branch rather than directly to the `main` branch of the fork.

Here is a step-by-step guide on how to achieve this:

### Prerequisites

Before you begin, ensure you have a local clone of your forked repository. As the New Relic OpenTelemetry Demo also operates a fork contribution model, you should normally have 3 remotes:

1. Your own repo origin
2. The `newrelic/opentelemetry-demo` origin, as `upstream`.
3. The `open-telemetry/opentelemetry-demo` origin, as `official`.

You should see something like the following (could be `https` instead of `ssh` if that method is preferred):

```bash
$ git remote -v                                                               
origin          git@github.com:{your_username}/opentelemetry-demo.git (fetch)
origin          git@github.com:{your_username}/opentelemetry-demo.git (push)
upstream        git@github.com:newrelic/opentelemetry-demo.git (fetch)
upstream        git@github.com:newrelic/opentelemetry-demo.git (push)
official        git@github.com:open-telemetry/opentelemetry-demo.git (fetch)
official        git@github.com:open-telemetry/opentelemetry-demo.git (push)
```

If `upstream` or `official` are missing, add them with:

```bash
git remote add upstream git@github.com:newrelic/opentelemetry-demo.git
git remote add official git@github.com:open-telemetry/opentelemetry-demo.git
```


### Step 1: Fetch the latest changes from the `official` and `upstream` remotes

This command downloads the latest commits and branches from the `upstream` and `official` repositories but does not merge them into your local branches.

```bash
git fetch upstream
git fetch official
```

### Step 2: Create a new branch for the sync

Create a new branch in your fork. This new branch will house the upstream changes and will be used to create the PR.

```ssh
git checkout -b sync_fork
```

### Step 3: Point your local branch's `HEAD` to the `main` on `upstream`

Ensure that your branch is synced with the latest `newrelic/opentelemetry-demo` default branch.

```bash
git reset --hard upstream/main
```

### Step 4: Merge the `official` changes into the new branch

Now, integrate the fetched changes from the `official` `main` (or default) branch into your newly created `sync_fork` branch.

```bash
git merge official/main
```

#### Sync to a specific release

In order to sync changes to a specific release of the OpenTelemetry Demo:

```bash
git fetch official --tags
git merge ${version}
```

Where `${version}` is the version/tag of the official OpenTelemetry Demo you want to sync to. 

#### Handling merge conflicts

If there are conflicts, Git will notify you.
You will need to resolve these conflicts manually, stage the resolved files (`git add .`), and complete the merge with a commit (`git commit`).

### Step 5: Adapt changes to work with New Relic's fork

There may be underlying changes to the official OpenTelemetry Demo that conflict with the code under `/newrelic`.
After syncing the fork, you can validate that New Relic's demo works as expected, and make changes as required.

The `scripts/update-docker.sh` script can help you update the synced `docker-compose.yml` to contain aspects needed for best integration with New Relic.
The `scripts/update-k8s.sh` script will change installation scripts to use the latest chart version, which may be needed when updating to the latest demo version.

You can commit any changes and include them in same PR in Step 6, so that user's of this demo get a working environment.

### Step 6: Push the new branch to your fork

Push the `sync_fork` branch, now containing the `official` updates, to your GitHub fork.

```bash
git push origin sync_fork
```

### Step 6: Create a Pull Request (PR)

Follow usual practice to raise a PR against `newrelic/opentemetry-demo`
This PR will show the changes between your New Relic's `main` branch and the `sync_fork` branch, which effectively represent the updates from the official repository.
It will also include any changes needed to adapt New Relic's fork after changes are made.
You can review the changes and merge the PR when ready, thus syncing your fork via a PR.

