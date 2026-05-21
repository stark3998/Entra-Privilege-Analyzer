// frontend/src/auth/msal.ts
import { PublicClientApplication, type Configuration } from "@azure/msal-browser";

const tenantId = import.meta.env.VITE_TENANT_ID || "common";

const msalConfig: Configuration = {
  auth: {
    clientId: import.meta.env.VITE_APP_CLIENT_ID || "",
    authority: `https://login.microsoftonline.com/${tenantId}`,
    redirectUri: window.location.origin,
    postLogoutRedirectUri: window.location.origin,
  },
  cache: {
    cacheLocation: "sessionStorage",
    storeAuthStateInCookie: false,
  },
};

let _msalInstance: PublicClientApplication | null = null;

export function getMsalInstance(): PublicClientApplication {
  if (!_msalInstance) {
    _msalInstance = new PublicClientApplication(msalConfig);
  }
  return _msalInstance;
}

export const msalInstance =
  import.meta.env.VITE_LOCAL_MODE === "true"
    ? (null as unknown as PublicClientApplication)
    : new PublicClientApplication(msalConfig);

/** Scopes for Microsoft Graph calls (profile info). */
export const graphScopes = ["User.Read"];

/** Scopes for backend API calls. */
export const apiScopes = [
  `api://${import.meta.env.VITE_APP_CLIENT_ID}/access_as_user`,
];
