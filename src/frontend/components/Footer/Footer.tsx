import * as S from './Footer.styled';

const Footer = () => {
  return (
    <S.Footer>
      <div>
        <p>This website is hosted for demo purpose only. It is not an actual shop.</p>
        <p>
          <span>session-id: 123</span>
        </p>
      </div>
      <p>
        @ 2022 OpenTelemetry (<a href="https://github.com/open-telemetry/opentelemetry-demo-webstore">Source Code</a>)
      </p>
    </S.Footer>
  );
};

export default Footer;
