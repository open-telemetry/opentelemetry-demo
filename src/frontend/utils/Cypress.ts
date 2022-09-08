export enum CypressFields {
  Ad = 'ad',
  CartDropdown = 'cart-dropdown',
  CartDropdownItem = 'cart-dropdown-item',
  CartDropdownItemQuantity = 'cart-dropdown-item-quantity',
  CartGoToShopping = 'cart-go-to-shopping',
  CartIcon = 'cart-icon',
  CartItemCount = 'cart-item-count',
  CheckoutPlaceOrder = 'checkout-place-order',
  CheckoutItem = 'checkout-item',
  CurrencySwitcher = 'currency-switcher',
  SessionId = 'session-id',
  ProductCard = 'product-card',
  ProductList = 'product-list',
  ProductPrice = 'product-price',
  RecommendationList = 'recommendation-list',
  HomePage = 'home-page',
  ProductDetail = 'product-detail',
  HotProducts = 'hot-products',
  ProductPicture = 'product-picture',
  ProductName = 'product-name',
  ProductDescription = 'product-description',
  ProductQuantity = 'product-quantity',
  ProductAddToCart = 'product-add-to-cart',
}

export const getElementByField = (field: CypressFields, context: Cypress.Chainable = cy) =>
  context.get(`[data-cy="${field}"]`);
