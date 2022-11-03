import * as S from './PlatformFlag.styled';

const { NEXT_PUBLIC_PLATFORM = 'local' } = typeof window !== 'undefined' ? window.ENV : {};

const platform = NEXT_PUBLIC_PLATFORM as S.Platform;

const PlatformFlag = () => {
  return (
    <S.PlatformFlag $platform={platform}>
      <S.Block $platform={platform}>local</S.Block>
    </S.PlatformFlag>
  );
};

export default PlatformFlag;
