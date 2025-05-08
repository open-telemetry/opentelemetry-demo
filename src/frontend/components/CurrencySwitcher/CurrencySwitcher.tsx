// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { useMemo, FC } from 'react';
import getSymbolFromCurrency from 'currency-symbol-map';
import { useCurrency } from '../../providers/Currency.provider';
import * as S from './CurrencySwitcher.styled';
import { CypressFields } from '../../utils/Cypress';

interface CurrencySwitcherProps {
  inDropdown?: boolean;
}

const CurrencySwitcher: FC<CurrencySwitcherProps> = ({ inDropdown = false }) => {
  const { currencyCodeList, setSelectedCurrency, selectedCurrency } = useCurrency();

  const currencySymbol = useMemo(() => getSymbolFromCurrency(selectedCurrency), [selectedCurrency]);

  return (
      <S.CurrencySwitcher>
        <S.Container>
          {inDropdown ? (
              <div onClick={(event) => setSelectedCurrency(selectedCurrency)}>
                金额转换 ({selectedCurrency})
              </div>
          ) : (
              <>
                <S.SelectedConcurrency>{currencySymbol}</S.SelectedConcurrency>
                <S.Select
                    name="currency_code"
                    onChange={(event: { target: { value: string } }) => setSelectedCurrency(event.target.value)}
                    value={selectedCurrency}
                    data-cy={CypressFields.CurrencySwitcher}
                >
                  {currencyCodeList.map(currencyCode => (
                      <option key={currencyCode} value={currencyCode}>
                        {currencyCode}
                      </option>
                  ))}
                </S.Select>
                <S.Arrow />
              </>
          )}
        </S.Container>
      </S.CurrencySwitcher>
  );
};

export default CurrencySwitcher;
