import { registerPlugin } from "@capacitor/core";

/**
 * Native StoreKit 2 bridge. The Swift implementation lives in
 * ios/App/CapApp-SPM/Sources/CapApp-SPM/PurangptIAPPlugin.swift and registers
 * under the same `jsName`. Method names here MUST match `pluginMethods` there.
 */

export interface IAPProduct {
  identifier: string;
  priceString: string;
  price: number;
  currencyCode: string;
  title: string;
  description: string;
}

export interface IAPPackage {
  identifier: string;
  product: IAPProduct;
}

export interface IAPOfferings {
  current: {
    monthly?: IAPPackage;
    annual?: IAPPackage;
    all?: IAPPackage[];
  } | null;
}

export interface IAPPurchaseResult {
  success: boolean;
  cancelled?: boolean;
  /** Signed JWS transaction representation for backend verification. */
  jws?: string;
}

export interface IAPEntitlements {
  isPro: boolean;
  jws?: string;
}

export interface PurangptIAPPlugin {
  getOfferings(): Promise<IAPOfferings>;
  purchasePackage(options: { productId: string }): Promise<IAPPurchaseResult>;
  restorePurchases(): Promise<IAPPurchaseResult>;
  getEntitlements(): Promise<IAPEntitlements>;
  addListener(
    eventName: "transactionUpdate",
    listenerFunc: () => void,
  ): Promise<{ remove: () => Promise<void> }>;
}

export const PurangptIAP = registerPlugin<PurangptIAPPlugin>("PurangptIAP");
