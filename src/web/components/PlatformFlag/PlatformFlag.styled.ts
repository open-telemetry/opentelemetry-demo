import styled from 'styled-components';

const getPlatformMap: Record<string, string> = {
  'aws-platform': '#ff9900',
  'onprem-platform': '#34A853',
  'gcp-platform': '#4285f4',
  'azure-platform': '#f35426',
  'alibaba-platform': '#ffC300',
  local: '#2c0678',
};

export const PlatformFlag = styled.div<{ $platform: string }>`
  position: fixed;
  top: 0;
  left: 0;
  width: 10px;
  height: 100vh;
  color: white;
  font-size: 24px;
  z-index: 999;

  background: ${({ $platform }) => getPlatformMap[$platform]};
`;

export const Block = styled.span<{ $platform: string }>`
  position: absolute;
  top: 98px;
  left: 0;
  width: 190px;
  height: 50px;
  display: flex;
  justify-content: center;
  align-items: center;

  background: ${({ $platform }) => getPlatformMap[$platform]};
`;
