import styled from 'styled-components';

export const Input = styled.input`
  width: -webkit-fill-available;
  border: none;
  border-bottom: 1px solid #9aa0a6;
  padding: 0 16px 8px 16px;
  outline: none;
  color: #1e2021;
`;

export const InputLabel = styled.label`
  width: -webkit-fill-available;
  margin: 0;
  padding: 8px 16px 0 16px;
  font-size: 12px;
  line-height: 1.8em;
  font-weight: normal;
  border-radius: 4px 4px 0px 0px;
  color: #5c6063;
  background-color: white;
  display: inline-block;
`;

export const Select = styled.select`
  width: 100%;
  border: none;
  border-bottom: 1px solid #9aa0a6;
  padding: 0 16px 8px 16px;
  outline: none;
  color: #1e2021;
`;

export const InputRow = styled.div`
  position: relative;
  margin-bottom: 24px;
  background: white;
`;

export const Arrow = styled.img.attrs({
  src: '/icons/Chevron.svg',
  alt: 'arrow',
})`
  position: absolute;
  right: 25px;
  width: 10px;
  height: 5px;
`;
