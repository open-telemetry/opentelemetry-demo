import styled from 'styled-components';

export const Header = styled.header`
  background-color: #853b5c;
  color: white;
`;

export const NavBar = styled.nav`
  padding-top: 5px;
  padding-bottom: 5px;

  display: flex;
  justify-content: center;
  font-size: 14px;
`;

export const SubNavBar = styled(NavBar)`
  height: 60px;
  background-color: white;
  font-size: 15px;
  color: #b4b2bb;
  box-shadow: 0px 0px 4px rgba(0, 0, 0, 0.25);
  z-index: 1;
  padding: 0;
`;

export const Container = styled.div`
  display: flex;
  justify-content: space-between;
  padding: 0 26px;
  width: 100%;
`;

export const NavBarBrand = styled.a`
  display: flex;
  align-items: center;
  padding: 0;

  img {
    height: 30px;
  }
`;

export const Controls = styled.div`
  display: flex;
  height: 60px;
`;
