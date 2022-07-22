import styled from 'styled-components';

export const CurrencySwitcher = styled.div`
  display: flex;
  justify-content: flex-end;
`;

export const Container = styled.div`
  display: flex;
  align-items: center;
  font-size: 12px;
  position: relative;
  margin-left: 40px;
  color: #605f64;

  &::-webkit-input-placeholder,
  &::-moz-placeholder,
  :-ms-input-placeholder,
  :-moz-placeholder {
    font-size: 12px;
    color: #605f64;
  }
`;

export const SelectedConcurrency = styled.span`
  font-size: 16px;
  text-align: center;

  position: relative;
  left: 35px;
  top: -1px;
  width: 20px;
  display: inline-block;
  height: 20px;
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

export const Select = styled.select`
  -webkit-appearance: none;
  -webkit-border-radius: 0px;

  display: flex;
  align-items: center;
  background: transparent;
  border-radius: 0;
  border: 1px solid #acacac;
  width: 130px;
  height: 40px;
  flex-shrink: 0;
  padding: 1px 0 0 45px;
  font-size: 16px;
  border-radius: 8px;
`;
