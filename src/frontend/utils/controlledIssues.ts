// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { addBreadcrumb, logError, logWarning } from './embrace';

export type IssueVariant =
  | 'profile_preferences_error'
  | 'product_recommendation_error'
  | 'cart_price_mismatch'
  | 'checkout_validation_error';

type AttributeValue = string | number | boolean;

const ISSUE_VARIANT_STORAGE_KEY = 'embrace_issue_variant';
const PERSONA_STORAGE_KEY = 'embrace_persona';
const FIRED_KEY_PREFIX = 'embrace_issue_fired_';
const AUTO_ENABLED_ENVIRONMENTS = new Set(['local', 'demo', 'internal']);

const AUTO_FIRE_PROBABILITY: Record<IssueVariant, number> = {
  profile_preferences_error: 0.2,
  product_recommendation_error: 0.35,
  cart_price_mismatch: 0.3,
  checkout_validation_error: 0.25,
};

function getWindowEnv(): Record<string, string | undefined> {
  if (typeof window === 'undefined') return {};

  return ((window as Window & { ENV?: Record<string, string | undefined> }).ENV || {});
}

function readEnv(key: string): string {
  return getWindowEnv()[key] || (typeof process !== 'undefined' ? process.env[key] || '' : '');
}

function readBooleanEnv(key: string): boolean | undefined {
  const value = readEnv(key).toLowerCase();
  if (['true', '1', 'yes'].includes(value)) return true;
  if (['false', '0', 'no'].includes(value)) return false;

  return undefined;
}

function getEnvironment(): string {
  return (
    readEnv('NEXT_PUBLIC_EMBRACE_ENVIRONMENT') ||
    readEnv('NEXT_PUBLIC_ENVIRONMENT') ||
    readEnv('NEXT_PUBLIC_PLATFORM') ||
    'local'
  ).toLowerCase();
}

function getAppVersion(): string {
  return (
    readEnv('NEXT_PUBLIC_EMBRACE_APP_VERSION') ||
    readEnv('NEXT_PUBLIC_APP_VERSION') ||
    'otel-demo-local'
  );
}

function getStorageValue(storage: Storage | undefined, key: string): string | null {
  try {
    return storage?.getItem(key) || null;
  } catch {
    return null;
  }
}

function setStorageValue(storage: Storage | undefined, key: string, value: string): void {
  try {
    storage?.setItem(key, value);
  } catch {
    // Ignore storage failures in privacy-restricted browser contexts.
  }
}

function isKnownIssueVariant(value: string | null): value is IssueVariant {
  return (
    value === 'profile_preferences_error' ||
    value === 'product_recommendation_error' ||
    value === 'cart_price_mismatch' ||
    value === 'checkout_validation_error'
  );
}

export function isDemoIssueEnabled(): boolean {
  return readBooleanEnv('NEXT_PUBLIC_ENABLE_DEMO_ISSUES') !== false;
}

export function isAutoDemoIssueEnabled(): boolean {
  const autoFlag = readBooleanEnv('NEXT_PUBLIC_AUTO_DEMO_ISSUES');
  const environment = getEnvironment();

  return Boolean(
    isDemoIssueEnabled() &&
    autoFlag === true &&
    environment !== 'production' &&
    AUTO_ENABLED_ENVIRONMENTS.has(environment)
  );
}

export function getDemoIssueVariant(): IssueVariant | null {
  if (typeof window === 'undefined' || !isDemoIssueEnabled()) return null;

  const params = new URLSearchParams(window.location.search);
  const localStore = typeof localStorage !== 'undefined' ? localStorage : undefined;
  const fromUrl = params.get('issue_variant');

  if (fromUrl) {
    if (!isKnownIssueVariant(fromUrl)) return null;
    setStorageValue(localStore, ISSUE_VARIANT_STORAGE_KEY, fromUrl);
    return fromUrl;
  }

  const fromStorage = getStorageValue(localStore, ISSUE_VARIANT_STORAGE_KEY);
  return isKnownIssueVariant(fromStorage) ? fromStorage : null;
}

function shouldInject(variant: IssueVariant): boolean {
  if (typeof window === 'undefined' || !isDemoIssueEnabled()) return false;

  const firedKey = `${FIRED_KEY_PREFIX}${variant}`;
  if (getStorageValue(sessionStorage, firedKey) === 'true') return false;

  const explicitVariant = getDemoIssueVariant();
  if (explicitVariant) return explicitVariant === variant;

  if (!isAutoDemoIssueEnabled()) return false;

  return Math.random() < AUTO_FIRE_PROBABILITY[variant];
}

function markAsFired(variant: IssueVariant): void {
  if (typeof window === 'undefined') return;
  setStorageValue(sessionStorage, `${FIRED_KEY_PREFIX}${variant}`, 'true');
}

function getPersona(): string {
  if (typeof window === 'undefined') return 'unknown';

  const params = new URLSearchParams(window.location.search);
  const localStore = typeof localStorage !== 'undefined' ? localStorage : undefined;
  const persona =
    params.get('user_persona') ||
    params.get('persona') ||
    getStorageValue(localStore, PERSONA_STORAGE_KEY) ||
    'unknown';

  if (params.has('user_persona') || params.has('persona')) {
    setStorageValue(localStore, PERSONA_STORAGE_KEY, persona);
  }

  return persona;
}

function getBaseAttributes(
  variant: IssueVariant,
  extras: Record<string, AttributeValue> = {}
): Record<string, AttributeValue> {
  return {
    app_version: getAppVersion(),
    demo_name: 'otel_astronomy_shop',
    environment: getEnvironment(),
    handled: true,
    issue_source: 'controlled_demo_issue',
    issue_variant: variant,
    user_persona: getPersona(),
    ...extras,
  };
}

interface RecommendationContext {
  page?: string;
  productId?: string;
}

export function maybeCaptureProductRecommendationError(context: RecommendationContext = {}): boolean {
  if (!shouldInject('product_recommendation_error')) return false;

  markAsFired('product_recommendation_error');
  addBreadcrumb('recommendations_load_started');

  const error = new TypeError("Cannot read properties of undefined (reading 'recommendedProducts')");
  logError(
    'product_recommendation_error',
    getBaseAttributes('product_recommendation_error', {
      component: 'Recommendations',
      function: 'loadRecommendations',
      page: context.page || '/product/[productId]',
      product_id: context.productId || 'unknown',
    }),
    error
  );

  addBreadcrumb('recommendations_fallback_used');
  return true;
}

interface CartPriceContext {
  cartId?: string;
  currency?: string;
  itemCount?: number;
  page?: string;
}

export function maybeCaptureCartPriceMismatchError(context: CartPriceContext = {}): void {
  if (!shouldInject('cart_price_mismatch')) return;

  markAsFired('cart_price_mismatch');
  addBreadcrumb('cart_subtotal_calculation_started');

  const currency = context.currency || 'USD';
  const error = new RangeError(`Failed to normalize cart subtotal for currency ${currency}`);
  logError(
    'cart_price_mismatch',
    getBaseAttributes('cart_price_mismatch', {
      cart_id: context.cartId || 'unknown',
      component: 'CartDetail',
      currency,
      function: 'normalizeCartSubtotal',
      item_count: context.itemCount ?? 0,
      page: context.page || '/cart',
    }),
    error
  );

  addBreadcrumb('cart_subtotal_fallback_used');
}

interface CheckoutValidationContext {
  city?: string;
  country?: string;
  page?: string;
  state?: string;
  zipCode?: string;
}

export function maybeCaptureCheckoutValidationError(context: CheckoutValidationContext = {}): void {
  if (!shouldInject('checkout_validation_error')) return;

  markAsFired('checkout_validation_error');
  addBreadcrumb('checkout_validation_started');

  const error = new Error('Shipping address validation returned an invalid schema');
  logError(
    'checkout_validation_error',
    getBaseAttributes('checkout_validation_error', {
      city: context.city || 'unknown',
      component: 'CheckoutForm',
      country: context.country || 'unknown',
      function: 'validateShippingAddress',
      page: context.page || '/cart',
      state: context.state || 'unknown',
      zip_code: context.zipCode || 'unknown',
    }),
    error
  );

  addBreadcrumb('checkout_validation_fallback_used');
}

interface PreferencesContext {
  page?: string;
}

export function maybeCaptureUserPreferencesError(context: PreferencesContext = {}): void {
  if (!shouldInject('profile_preferences_error')) return;

  markAsFired('profile_preferences_error');
  addBreadcrumb('user_preferences_load_started');

  const error = new SyntaxError('Failed to parse stored user preferences');
  logWarning(
    'profile_preferences_error',
    getBaseAttributes('profile_preferences_error', {
      component: 'App',
      error_message: error.message,
      error_name: error.name,
      function: 'loadUserPreferences',
      page: context.page || '/',
    })
  );

  addBreadcrumb('user_preferences_fallback_used');
}
