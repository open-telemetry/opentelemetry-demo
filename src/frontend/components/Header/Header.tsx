import { useState, useEffect } from 'react';
import CartIcon from '../CartIcon';
import CurrencySwitcher from '../CurrencySwitcher';
import * as S from './Header.styled';
import { checkAuth, logout } from '../../utils/auth';
import { useRouter } from 'next/router';
import Link from 'next/link';

const Header = () => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const router = useRouter();

  useEffect(() => {
    setIsAuthenticated(checkAuth());
  }, [router.pathname]);

  const handleLogout = async () => {
    try {
      await logout();
      setIsDropdownOpen(false);
      router.push('/');
    } catch (error) {
      console.error('注销失败:', error);
    }
  };

  const toggleDropdown = () => {
    setIsDropdownOpen(!isDropdownOpen);
  };

  return (
      <S.Header>
        <S.NavBar>
          <S.Container>
            <S.NavBarBrand href="/">
              <S.BrandImg />
            </S.NavBarBrand>
            <S.Controls>
              <S.AvatarContainer onClick={toggleDropdown}>
                <S.Avatar src="/images/avatar.png" alt="User" />
                {isDropdownOpen && (
                    <S.Dropdown>
                      {isAuthenticated ? (
                          <>
                            <S.DropdownItem>
                              <Link href="/cart" onClick={() => setIsDropdownOpen(false)}>
                                购物车
                              </Link>
                            </S.DropdownItem>
                            <S.DropdownItem>
                              <div onClick={() => setIsDropdownOpen(false)}>
                                <CurrencySwitcher inDropdown={true} />
                              </div>
                            </S.DropdownItem>
                            <S.DropdownItem onClick={handleLogout}>
                              注销
                            </S.DropdownItem>
                          </>
                      ) : (
                          <S.DropdownItem>
                            <Link href="/login" onClick={() => setIsDropdownOpen(false)}>
                              登录
                            </Link>
                          </S.DropdownItem>
                      )}
                    </S.Dropdown>
                )}
              </S.AvatarContainer>
            </S.Controls>
          </S.Container>
        </S.NavBar>
      </S.Header>
  );
};

export default Header;