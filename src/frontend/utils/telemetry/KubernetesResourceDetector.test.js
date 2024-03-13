const KubernetesResourceDetector = require('./KubernetesResourceDetector');
const { SemanticResourceAttributes } = require('@opentelemetry/semantic-conventions');
const { expect, test } = require('@jest/globals');
const mock = require('mock-fs');

const K8S_POD_ID = '6189e731-8c9a-4c3a-ba6f-9796664788a8';

const trimMultiline = s =>
  s
    .split('\n')
    .map(s => s.trim())
    .join('\n');

describe('KubernetesResourceDetector', () => {
  afterEach(() => {
    mock.restore();
  });

  describe('not on Kubernetes', () => {
    test('returns an empty resource', async () => {
      const resource = await new KubernetesResourceDetector().detect();
      expect(Object.keys(resource.attributes)).toHaveLength(0);
    });
  });

  describe('on Kubernetes', () => {
    describe('with cgroup v1', () => {
      test('detects the Pod UID correctly', async () => {
        mock({
          '/etc/hosts': trimMultiline(`# Kubernetes-managed hosts file.
            127.0.0.1       localhost
            255.255.255.255 broadcasthost`),
          '/proc/self/mountinfo':
            trimMultiline(`564 446 0:164 / / rw,relatime master:190 - overlay overlay rw,lowerdir=/var/lib/docker/bogusPodIdThatShouldNotBeOneSetBecauseTheFirstOneWasPicked
            565 564 0:166 / /proc rw,nosuid,nodev,noexec,relatime - proc proc rw
            566 564 0:338 / /dev rw,nosuid - tmpfs tmpfs rw,size=65536k,mode=755
            567 566 0:339 / /dev/pts rw,nosuid,noexec,relatime - devpts devpts rw,gid=5,mode=620,ptmxmode=666
            568 564 0:161 / /sys ro,nosuid,nodev,noexec,relatime - sysfs sysfs ro
            569 568 0:30 / /sys/fs/cgroup ro,nosuid,nodev,noexec,relatime - cgroup2 cgroup rw
            570 566 0:157 / /dev/mqueue rw,nosuid,nodev,noexec,relatime - mqueue mqueue rw
            571 566 254:1 /docker/volumes/minikube/_data/lib/kubelet/pods/6189e731-8c9a-4c3a-ba6f-9796664788a8/containers/my-shell/0447d6c5 /dev/termination-log rw,relatime - ext4 /dev/vda1 rw
            572 564 254:1 /docker/volumes/minikube/_data/lib/docker/containers/bogusPodIdThatShouldNotBeOneSetBecauseTheFirstOneWasPicked
            573 564 254:1 /docker/volumes/minikube/_data/lib/docker/containers/bogusPodIdThatShouldNotBeOneSetBecauseTheFirstOneWasPicked
            574 564 254:1 /docker/volumes/minikube/_data/lib/kubelet/pods/6189e731-8c9a-4c3a-ba6f-9796664788a8/etc-hosts /etc/hosts rw,relatime - ext4 /dev/vda1 rw
            575 566 0:156 / /bogusPodIdThatShouldNotBeOneSetBecauseTheFirstOneWasPicked
            576 564 0:153 / /bogusPodIdThatShouldNotBeOneSetBecauseTheFirstOneWasPicked
            447 566 0:339 /0 /bogusPodIdThatShouldNotBeOneSetBecauseTheFirstOneWasPicked
            448 565 0:166 /bus /bogusPodIdThatShouldNotBeOneSetBecauseTheFirstOneWasPicked
            450 565 0:166 /irq /bogusPodIdThatShouldNotBeOneSetBecauseTheFirstOneWasPicked
            451 565 0:166 /sys /bogusPodIdThatShouldNotBeOneSetBecauseTheFirstOneWasPicked
            452 565 0:166 /sysrq-trigger /bogusPodIdThatShouldNotBeOneSetBecauseTheFirstOneWasPicked`),
        });

        const resource = await new KubernetesResourceDetector().detect();

        expect(resource.attributes[SemanticResourceAttributes.K8S_POD_UID]).toEqual(K8S_POD_ID);
      });
    });

    describe('with cgroup v2', () => {
      test('detects the Pod UID correctly', async () => {
        mock({
          '/etc/hosts': trimMultiline(`# Kubernetes-managed hosts file.
            127.0.0.1       localhost
            255.255.255.255 broadcasthost`),
          '/proc/self/cgroup':
            trimMultiline(`14:name=systemd:/docker/c24aa3879860ee981d29f0492aef1e39c45d7c7fcdff7bd2050047d0bd390311/kubepods/besteffort/pod6189e731-8c9a-4c3a-ba6f-9796664788a8/bogusPodIdThatShouldNotBeOneSetBecauseTheFirstOneWasPicked
            13:rdma:/kubepods/besteffort/pod6189e731-8c9a-4c3a-ba6f-9796664788a8/bogusPodIdThatShouldNotBeOneSetBecauseTheFirstOneWasPicked
            12:pids:/docker/c24aa3879860ee981d29f0492aef1e39c45d7c7fcdff7bd2050047d0bd390311/kubepods/besteffort/pod6189e731-8c9a-4c3a-ba6f-9796664788a8/bogusPodIdThatShouldNotBeOneSetBecauseTheFirstOneWasPicked
            11:hugetlb:/docker/c24aa3879860ee981d29f0492aef1e39c45d7c7fcdff7bd2050047d0bd390311/kubepods/besteffort/pod6189e731-8c9a-4c3a-ba6f-9796664788a8/bogusPodIdThatShouldNotBeOneSetBecauseTheFirstOneWasPicked
            10:net_prio:/docker/c24aa3879860ee981d29f0492aef1e39c45d7c7fcdff7bd2050047d0bd390311/kubepods/besteffort/pod6189e731-8c9a-4c3a-ba6f-9796664788a8/bogusPodIdThatShouldNotBeOneSetBecauseTheFirstOneWasPicked
            9:perf_event:/docker/c24aa3879860ee981d29f0492aef1e39c45d7c7fcdff7bd2050047d0bd390311/kubepods/besteffort/pod6189e731-8c9a-4c3a-ba6f-9796664788a8/bogusPodIdThatShouldNotBeOneSetBecauseTheFirstOneWasPicked
            8:net_cls:/docker/c24aa3879860ee981d29f0492aef1e39c45d7c7fcdff7bd2050047d0bd390311/kubepods/besteffort/pod6189e731-8c9a-4c3a-ba6f-9796664788a8/bogusPodIdThatShouldNotBeOneSetBecauseTheFirstOneWasPicked
            7:freezer:/docker/c24aa3879860ee981d29f0492aef1e39c45d7c7fcdff7bd2050047d0bd390311/kubepods/besteffort/pod6189e731-8c9a-4c3a-ba6f-9796664788a8/bogusPodIdThatShouldNotBeOneSetBecauseTheFirstOneWasPicked
            6:devices:/docker/c24aa3879860ee981d29f0492aef1e39c45d7c7fcdff7bd2050047d0bd390311/kubepods/besteffort/pod6189e731-8c9a-4c3a-ba6f-9796664788a8/bogusPodIdThatShouldNotBeOneSetBecauseTheFirstOneWasPicked
            5:memory:/docker/c24aa3879860ee981d29f0492aef1e39c45d7c7fcdff7bd2050047d0bd390311/kubepods/besteffort/pod6189e731-8c9a-4c3a-ba6f-9796664788a8/bogusPodIdThatShouldNotBeOneSetBecauseTheFirstOneWasPicked
            4:blkio:/docker/c24aa3879860ee981d29f0492aef1e39c45d7c7fcdff7bd2050047d0bd390311/kubepods/besteffort/pod6189e731-8c9a-4c3a-ba6f-9796664788a8/bogusPodIdThatShouldNotBeOneSetBecauseTheFirstOneWasPicked
            3:cpuacct:/docker/c24aa3879860ee981d29f0492aef1e39c45d7c7fcdff7bd2050047d0bd390311/kubepods/besteffort/pod6189e731-8c9a-4c3a-ba6f-9796664788a8/bogusPodIdThatShouldNotBeOneSetBecauseTheFirstOneWasPicked
            2:cpu:/docker/c24aa3879860ee981d29f0492aef1e39c45d7c7fcdff7bd2050047d0bd390311/kubepods/besteffort/pod6189e731-8c9a-4c3a-ba6f-9796664788a8/bogusPodIdThatShouldNotBeOneSetBecauseTheFirstOneWasPicked
            1:cpuset:/docker/c24aa3879860ee981d29f0492aef1e39c45d7c7fcdff7bd2050047d0bd390311/kubepods/besteffort/pod6189e731-8c9a-4c3a-ba6f-9796664788a8/bogusPodIdThatShouldNotBeOneSetBecauseTheFirstOneWasPicked
            0::/kubepods/besteffort/pod6189e731-8c9a-4c3a-ba6f-9796664788a8/bogusPodIdThatShouldNotBeOneSetBecauseTheFirstOneWasPicked`),
        });

        const resource = await new KubernetesResourceDetector().detect();

        expect(resource.attributes[SemanticResourceAttributes.K8S_POD_UID]).toEqual(K8S_POD_ID);
      });
    });
  });
});
