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
      <S.FooterTop>
        <div>
          <p>This website is hosted for demo purposes only. It is not an actual shop. This is not a Google product.</p>
          <p>
            @ 2022 OpenTelemetry (
            <a href="https://github.com/open-telemetry/opentelemetry-demo-webstore">Source Code</a>)
          </p>
          <p>
            <small>
              <span>session-id: {sessionId}</span> - <span>request-id: {requestId}</span>
            </small>
            <br />
            <small>
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
            </small>
          </p>
        </div>
      </S.FooterTop>
    </S.Footer>
  );
};

export default Footer;
