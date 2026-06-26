function response = postRunStateCoaching(baseUrl, payload, timeoutSeconds, accessToken)
%POSTRUNSTATECOACHING Send a run-state coaching request to the bridge endpoint.

mxa.bridge.validateBaseUrl(baseUrl);
base = char(strip(string(baseUrl)));
while endsWith(base, "/")
    base = base(1:end-1);
end
endpoint = char(string(base) + "/api/v1/bridge/run-state/coaching");
tokenText = string(accessToken);
if strlength(tokenText) == 0
    error("mxa:bridge:AuthTokenMissing", "run-state coaching access token is required.");
end
options = weboptions( ...
    "MediaType", "application/json", ...
    "HeaderFields", ["Authorization", "Bearer " + tokenText], ...
    "Timeout", timeoutSeconds);

response = webwrite(endpoint, payload, options);
end
