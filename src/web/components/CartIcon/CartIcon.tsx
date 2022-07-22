import { useCart } from '../../providers/Cart.provider';
import * as S from './CartIcon.styled';

const CartIcon = () => {
  const {
    cart: { items },
  } = useCart();

  return (
    <S.CartIcon href="/cart">
      <>
        <S.Icon src="/icons/Hipster_CartIcon.svg" alt="Cart icon" title="Cart" />
        {!!items.length && <S.ItemsCount>{items.length}</S.ItemsCount>}
      </>
    </S.CartIcon>
  );
};

export default CartIcon;
