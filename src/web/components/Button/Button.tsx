import styled, { css } from 'styled-components';

const Button = styled.button<{ $type?: 'primary' | 'secondary' }>`
  background-color: #ce0631;
  color: white;
  display: inline-block;
  border: solid 1px #ce0631;
  padding: 8px 16px;
  outline: none;
  font-size: 14px;
  border-radius: 22px;
  cursor: pointer;

  ${({ $type = 'primary' }) =>
    $type === 'secondary' &&
    css`
      background: none;
      color: #ce0631;
    `};
`;

export default Button;
