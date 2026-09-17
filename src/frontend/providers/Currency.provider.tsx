// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { createContext, useCallback, useContext, useMemo, useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import ApiGateway from '../gateways/Api.gateway';
import SessionGateway from '../gateways/Session.gateway';

const { currencyCode } = SessionGateway.getSession();

interface IContext {
  currencyCodeList: string[];
  setSelectedCurrency(currency: string): void;
  selectedCurrency: string;
}

export const Context = createContext<IContext>({
  currencyCodeList: [],
  selectedCurrency: 'USD',
  setSelectedCurrency: () => ({}),
});

interface IProps {
  children: React.ReactNode;
}

export const useCurrency = () => useContext(Context);

const CurrencyProvider = ({ children }: IProps) => {
  const { data: currencyCodeListUnsorted = [] } = useQuery({
    queryKey: ['currency'],
    queryFn: ApiGateway.getSupportedCurrencyList
  });
  const [selectedCurrency, setSelectedCurrency] = useState<string>('');

  const onSelectCurrency = useCallback((currency: string) => {
    setSelectedCurrency(currency);
    SessionGateway.setSessionValue('currencyCode', currency);
  }, []);

  const currencyCodeList = useMemo(() => [...currencyCodeListUnsorted].sort(), [currencyCodeListUnsorted]);

  useEffect(() => {
    const sessionCurrency = currencyCode || 'USD';
    if (currencyCodeList.length > 0) {
      const activeCurrency = selectedCurrency || sessionCurrency;
      if (!currencyCodeList.includes(activeCurrency)) {
        onSelectCurrency('USD');
      } else if (!selectedCurrency) {
        setSelectedCurrency(sessionCurrency);
      }
    } else if (!selectedCurrency) {
      setSelectedCurrency(sessionCurrency);
    }
  }, [currencyCodeList, selectedCurrency, onSelectCurrency]);

  const value = useMemo(
      () => ({
        currencyCodeList,
        selectedCurrency,
        setSelectedCurrency: onSelectCurrency,
      }),
      [currencyCodeList, selectedCurrency, onSelectCurrency]
  );

  return <Context.Provider value={value}>{children}</Context.Provider>;
};

export default CurrencyProvider;
