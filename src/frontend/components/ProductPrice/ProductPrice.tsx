import { useMemo } from 'react';
import getSymbolFromCurrency from 'currency-symbol-map';
import { Money } from '../../protos/demo';
import { useCurrency } from '../../providers/Currency.provider';
import { CypressFields } from '../../utils/Cypress';

interface IProps {
  price: Money;
}

const ProductPrice = ({ price: { units, currencyCode, nanos } }: IProps) => {
  const { selectedCurrency } = useCurrency();

  const currencySymbol = useMemo(
    () => getSymbolFromCurrency(currencyCode) || selectedCurrency,
    [currencyCode, selectedCurrency]
  );

  const total = units + nanos / 1000000000;

  return (
    <span data-cy={CypressFields.ProductPrice}>
      {currencySymbol} {total.toFixed(2)}
    </span>
  );
};

export default ProductPrice;
