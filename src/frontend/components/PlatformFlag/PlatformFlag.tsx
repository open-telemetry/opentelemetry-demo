import { useQuery } from 'react-query';
import ApiGateway from '../../gateways/Api.gateway';
import * as S from './PlatformFlag.styled';

const PlatformFlag = () => {
  const { data: { ENV_PLATFORM = 'local' } = {} } = useQuery('config', () => ApiGateway.getConfig());

  const platform = ENV_PLATFORM as S.Platform;

  return (
    <S.PlatformFlag $platform={platform}>
      <S.Block $platform={platform}>local</S.Block>
    </S.PlatformFlag>
  );
};

export default PlatformFlag;
