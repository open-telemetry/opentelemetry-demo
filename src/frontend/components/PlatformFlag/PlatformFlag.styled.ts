// Copyright The OpenTelemetry Authors
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

import styled from 'styled-components';

export const Block = styled.div`
  position: absolute;
  bottom: 0;
  right: 0;
  width: 100px;
  height: 27px;
  display: flex;
  justify-content: center;
  align-items: center;
  font-size: ${({ theme }) => theme.sizes.mSmall};
  font-weight: ${({ theme }) => theme.fonts.regular};
  color: ${({ theme }) => theme.colors.white};
  background: ${({ theme }) => theme.colors.otelYellow};

  ${({ theme }) => theme.breakpoints.desktop} {
    width: 190px;
    height: 50px;
    font-size: ${({ theme }) => theme.sizes.dSmall};
  }
`;
