import CartIcon from '../CartIcon';
import CurrencySwitcher from '../CurrencySwitcher';
import * as S from './Header.styled';

const Header = () => {
  return (
    <S.Header>
      <S.SubNavBar>
        <S.Container>
          <S.NavBarBrand href="/">
            <img src="/icons/Hipster_NavLogo.svg" alt="" />
          </S.NavBarBrand>
          <S.Controls>
            <CurrencySwitcher />
            <CartIcon />
          </S.Controls>
        </S.Container>
      </S.SubNavBar>
    </S.Header>
  );
};

export default Header;
