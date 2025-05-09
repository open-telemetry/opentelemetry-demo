import { useState, useEffect } from 'react';
import CurrencySwitcher from '../CurrencySwitcher';
import * as S from './Header.styled';
import { checkAuth, logout } from '../../utils/auth';
import { useRouter } from 'next/router';
import Link from 'next/link';

const Header = () => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [showCurrencySwitcher, setShowCurrencySwitcher] = useState(false); // 新增状态

  const router = useRouter();

  useEffect(() => {
    setIsAuthenticated(checkAuth());
  }, [router.pathname]);

  const handleLogout = async () => {
    try {
      await logout();
      setIsDropdownOpen(false);
      router.push('/').then(() => window.location.reload());
    } catch (error) {
      console.error('注销失败:', error);
    }
  };

  const handleOrdersClick = () => {
    router.push('/orders');
    setIsDropdownOpen(false);
  };

  const toggleDropdown = () => {
    setIsDropdownOpen(!isDropdownOpen);
  };

  const toggleCurrencySwitcher = () => {
    setShowCurrencySwitcher(!showCurrencySwitcher);
    setIsDropdownOpen(false); // 关闭下拉菜单
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
              <S.Avatar src="/icons/user.png" alt="User" />
              {isDropdownOpen && (
                <S.Dropdown>
                  {isAuthenticated ? (
                    <>
                      <S.DropdownItem>
                        <Link href="/cart" onClick={() => setIsDropdownOpen(false)}>
                          购物车
                        </Link>
                      </S.DropdownItem>
                      <S.DropdownItem onClick={toggleCurrencySwitcher}>
                        币种转换
                      </S.DropdownItem>
                      <S.DropdownItem onClick={handleLogout}>
                        注销
                      </S.DropdownItem>
                      <S.DropdownItem onClick={handleOrdersClick}>
                        订单
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
            {showCurrencySwitcher && (
              <CurrencySwitcher />
            )}
          </S.Controls>
        </S.Container>
      </S.NavBar>
    </S.Header>
  );
};

export default Header;