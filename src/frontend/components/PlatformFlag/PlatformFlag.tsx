import * as S from './PlatformFlag.styled';

const platform = (process.env.NEXT_PUBLIC_ANALYTICS_ID || 'local') as S.Platform;

const PlatformFlag = () => {
  return (
    <S.PlatformFlag $platform={platform}>
      <S.Block $platform={platform}>local</S.Block>
    </S.PlatformFlag>
  );
};

export default PlatformFlag;
