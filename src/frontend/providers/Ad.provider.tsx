// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { createContext, useContext, useMemo } from 'react';
import { useQuery } from 'react-query';
import ApiGateway from '../gateways/Api.gateway';
import { Ad, Money, Product } from '../protos/demo';
import { useCurrency } from './Currency.provider';

interface IContext {
  recommendedProductList: Product[];
  adList: Ad[];
}

export const Context = createContext<IContext>({
  recommendedProductList: [],
  adList: [],
});

interface IProps {
  children: React.ReactNode;
  productIds: string[];
  contextKeys: string[];
}

export const useAd = () => useContext(Context);

const AdProvider = ({ children, productIds, contextKeys }: IProps) => {
  const { selectedCurrency } = useCurrency();
  const { data: adList = [] } = useQuery(
    ['ads', contextKeys],
    () => {
      if (contextKeys.length === 0) {
        return Promise.resolve([]);
      } else {
        return ApiGateway.listAds(contextKeys);
      }
    },
    {
      refetchOnWindowFocus: false,
    }
  );
  const { data: recommendedProductList = [] } = useQuery(
    ['recommendations', productIds, 'selectedCurrency', selectedCurrency],
    () => ApiGateway.listRecommendations(productIds, selectedCurrency),
    {
      refetchOnWindowFocus: false,
    }
  );

  const value = useMemo(
    () => ({
      adList,
      recommendedProductList,
    }),
    [adList, recommendedProductList]
  );

  return <Context.Provider value={value}>{children}</Context.Provider>;
};

export default AdProvider;
