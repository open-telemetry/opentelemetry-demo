// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import ApiGateway from '../gateways/Api.gateway';
import SessionGateway from '../gateways/Session.gateway';
import useClientValue from '../utils/hooks/useClientValue';

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
  const sessionCurrency = useClientValue(() => currencyCode, '');
  const [chosenCurrency, setChosenCurrency] = useState<string | null>(null);
  const selectedCurrency = chosenCurrency ?? sessionCurrency;

  const onSelectCurrency = useCallback((currencyCode: string) => {
    setChosenCurrency(currencyCode);
    SessionGateway.setSessionValue('currencyCode', currencyCode);
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
