function token = defaultTokenProvider(varargin)
%DEFAULTTOKENPROVIDER Fail closed until the host injects a token provider.

token = "";
error("mxa:bridge:TokenProviderMissing", "run-state token provider is required.");
end
