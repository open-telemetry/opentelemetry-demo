// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { useRouter } from 'next/router';
import { useState, useEffect } from 'react';
import CartIcon from '../CartIcon';
import CurrencySwitcher from '../CurrencySwitcher';
import * as S from './Header.styled';

const Header = () => {
  const router = useRouter();
  const [isResetting, setIsResetting] = useState(false);

  const handleLogoClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
    // Only reset session if currently on home page (for demo purposes)
    if (router.pathname === '/' && typeof window !== 'undefined' && window.localStorage) {
      e.preventDefault(); // Prevent navigation

      // Flash "resetting" message
      setIsResetting(true);

      // Remove old session
      localStorage.removeItem('session');
      console.log('🔄 Session reset - generating new user...');

      // Immediately regenerate new session and RUM attributes
      // This calls the same function from global-attributes.js
      if (typeof (window as any).getSplunkGlobalAttributes === 'function') {
        const newAttributes = (window as any).getSplunkGlobalAttributes();
        console.log('✅ New user generated:', newAttributes);

        // Update RUM with new attributes if possible
        if (typeof (window as any).SplunkRum !== 'undefined') {
          try {
            (window as any).SplunkRum.setGlobalAttributes(newAttributes);
            console.log('✅ RUM global attributes updated for current session');
          } catch (err) {
            console.log('ℹ️ RUM attributes will be applied on next page load');
          }
        }
      }

      // Reload page after brief flash to fully apply changes
      setTimeout(() => {
        window.location.href = '/';
      }, 500);
    }
    // On other pages, allow normal navigation without resetting session
  };

  // Clear resetting state if it gets stuck
  useEffect(() => {
    if (isResetting) {
      const timeout = setTimeout(() => setIsResetting(false), 1000);
      return () => clearTimeout(timeout);
    }
  }, [isResetting]);

  return (
    <S.Header>
      {isResetting && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.7)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 9999,
          color: 'white',
          fontSize: '24px',
          fontWeight: 'bold'
        }}>
          🔄 Resetting User...
        </div>
      )}
      <S.NavBar>
        <S.Container>
          <S.NavBarBrand href="/" onClick={handleLogoClick}>
            <S.BrandImg />
          </S.NavBarBrand>
          <S.Controls>
            <CurrencySwitcher />
            <CartIcon />
          </S.Controls>
        </S.Container>
      </S.NavBar>
    </S.Header>
  );
};

export default Header;
