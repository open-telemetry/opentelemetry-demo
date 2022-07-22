import * as S from './PlatformFlag.styled';

const PlatformFlag = () => {
  return (
    <S.PlatformFlag $platform="local">
      <S.Block $platform="local">local</S.Block>
    </S.PlatformFlag>
  );
};

export default PlatformFlag;
