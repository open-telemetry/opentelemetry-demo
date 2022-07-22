import { Product } from '../../protos/demo';
import ProductPrice from '../ProductPrice';
import * as S from './ProductCard.styled';

interface IProps {
  product: Product;
}

const ProductCard = ({
  product: {
    id,
    picture,
    name,
    priceUsd = {
      currencyCode: 'USD',
      units: 0,
      nanos: 0,
    },
  },
}: IProps) => {
  return (
    <S.ProductCard>
      <S.Link href={`/product/${id}`}>
        <>
          <S.Image alt={name} src={picture} />
          <S.Overlay />
        </>
      </S.Link>
      <div>
        <S.ProductName>{name}</S.ProductName>
        <ProductPrice price={priceUsd} />
      </div>
    </S.ProductCard>
  );
};

export default ProductCard;
