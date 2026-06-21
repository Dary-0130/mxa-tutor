function validateBaseUrl(baseUrl)
%VALIDATEBASEURL Enforce the TASK-510 URL boundary for the bridge client.

uriText = char(strip(string(baseUrl)));
try
    uri = java.net.URI(uriText);
catch
    throwInvalid();
end

scheme = lower(javaStringToString(uri.getScheme()));
host = javaStringToString(uri.getHost());
userinfo = javaStringToString(uri.getUserInfo());

if strlength(scheme) == 0 || strlength(host) == 0
    throwInvalid();
end
if strlength(userinfo) > 0
    throwInvalid();
end
if scheme == "http"
    if host ~= "localhost"
        throwInvalid();
    end
    return
end
if scheme == "https"
    return
end
throwInvalid();
end

function value = javaStringToString(javaValue)
if isempty(javaValue)
    value = "";
else
    value = string(char(javaValue));
end
end

function throwInvalid()
error( ...
    "mxa:bridge:InvalidBaseUrl", ...
    "BaseUrl must be http://localhost or an https URL without userinfo.");
end
