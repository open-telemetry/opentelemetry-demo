/* eslint-disable @typescript-eslint/no-unused-vars */
import { readFile } from 'fs/promises';
import { Detector, Resource, ResourceDetectionConfig } from '@opentelemetry/resources';
import { SemanticResourceAttributes } from '@opentelemetry/semantic-conventions';

const POD_ID_LENGTH = 36;
const CONTAINER_ID_LENGTH = 64;

export class KubernetesResourceDetector implements Detector {
  async detect(_config?: ResourceDetectionConfig): Promise<Resource> {
    try {
      const hostFileContent = await readFile('/etc/hosts', {
        encoding: 'utf8',
      });

      const hostFileFirstLine = String(hostFileContent).slice(0, hostFileContent.indexOf('\n'));
      if (!hostFileFirstLine.startsWith('# Kubernetes-managed hosts file')) {
        // logger.debug(
        //   'File /etc/hosts does not seem managed by Kubernetes, thus KubernetesResourceDetector does not think this process runs in a Kubernetes pod.'
        // );
        return Resource.EMPTY;
      }
    } catch (ex) {
      // logger.debug(
      //   'Encountered an error, KubernetesResourceDetector will assume this process does not run in a Kubernetes pod.'
      // );
      return Resource.EMPTY;
    }

    let podUid: string | null | undefined = null;
    try {
      podUid = await readPodUidCgroupsV1();
    } catch (err) {
      try {
        // logger.debug(`No Pod UID v1 found: ${err}`);
        podUid = await readPodUidCgroupsV2();
      } catch (err) {
        // logger.debug(`No Pod UID v2 found: ${err}`);
      }
    }

    if (!podUid) {
      return Resource.EMPTY;
    }

    return new Resource({
      [SemanticResourceAttributes.K8S_POD_UID]: podUid,
    });
  }
}

const readPodUidCgroupsV1 = async (): Promise<string> => {
  const mountinfo = await readFile('/proc/self/mountinfo', {
    encoding: 'utf8',
  });

  const podMountInfoEntry = mountinfo
    .split('\n')
    .map(line => line.trim())
    .filter(line => !!line)
    .filter(line => line.length > POD_ID_LENGTH)
    .find(line => line.indexOf('/pods/') > 0);

  if (!podMountInfoEntry) {
    return Promise.reject(new Error("No pod-like mountpoint found in '/proc/self/mountinfo'"));
  }

  return podMountInfoEntry.split('/pods/')[1].substring(0, POD_ID_LENGTH);
};

const readPodUidCgroupsV2 = async (): Promise<string | null | undefined> => {
  const cgroups = await readFile('/proc/self/cgroup', {
    encoding: 'utf8',
  });

  if (!cgroups) {
    return null;
  }
  return cgroups
    .split('\n')
    .map(line => line.trim())
    .filter(line => !!line)
    .filter(line => line.length > CONTAINER_ID_LENGTH)
    .map(line => {
      const segments = line.split('/');
      if (
        segments.length > 2 &&
        segments[segments.length - 2].startsWith('pod') &&
        segments[segments.length - 2].length === POD_ID_LENGTH + 3
      ) {
        return segments[segments.length - 2].substring(3, POD_ID_LENGTH + 3);
      }

      return segments[segments.length - 2];
    })
    .find(podUid => !!podUid);
};
