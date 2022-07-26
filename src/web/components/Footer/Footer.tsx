import * as S from './Footer.styled';

const sessionId = '123';
const requestId = '1234';

const deploymentDetails = {
  pod: '123',
  zone: '',
  clusterName: '',
};

const Footer = () => {
  return (
    <S.Footer>
      <div>
        <p>This website is hosted for demo purpose only. It is not an actual shop. This is not a Google product</p>
        <p>
          <span>session-id: {sessionId}</span> - <span>request-id: {requestId}</span>
          <br />
          <b>Cluster: </b>
          {deploymentDetails.clusterName}
          <br />
          <b>Zone: </b>
          {deploymentDetails.zone}
          <br />
          <b>Pod: </b>
          {deploymentDetails.pod}
          <br />
          Deployment details are still loading. Try refreshing this page.
        </p>
      </div>
      <p>
        @ 2022 OpenTelemetry (<a href="https://github.com/open-telemetry/opentelemetry-demo-webstore">Source Code</a>)
      </p>
    </S.Footer>
  );
};

export default Footer;
