// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { createContext, useCallback, useContext, useMemo, useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import ApiGateway from '../gateways/Api.gateway';
import SessionGateway from '../gateways/Session.gateway';
import { sendEvent } from '@dash0/sdk-web';

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
    queryFn: ApiGateway.getSupportedCurrencyList,
  });
  const [selectedCurrency, setSelectedCurrency] = useState<string>('');

  useEffect(() => {
    setSelectedCurrency(currencyCode);
  }, []);

  const onSelectCurrency = useCallback((currencyCode: string) => {
    setSelectedCurrency(currencyCode);
    SessionGateway.setSessionValue('currencyCode', currencyCode);
    sendEvent('currency_switched', { attributes: { currencyCode } });
  }, []);

  const currencyCodeList = currencyCodeListUnsorted.sort();

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
