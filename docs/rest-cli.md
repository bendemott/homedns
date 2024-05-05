# Using the Rest Command Line
The DNS Server comes with a Rest API.
That REST API can be accessed using a command line interface installed on the path
as `homedns-api`

## Authenticating
By default, a request for a record, and to authenticate at the same time will look like:

```shell
homedns-api \
    --server localhost:443 \
    --no-verify \
    --jwt-subject "0aaa1111-1111-1a1a-a111-aa11aa11111a" \
    --jwt-key ./jwt-key.pem \
    A GET "mydomain.com"
```

Fortunately you can configure environment variables so you don't have to repeat credentials in each command.

See: [jwt-auth](jwt-auth.md)

Here's an example of the typical required environment variables required to authenticate with JWT
```shell
export HOMEDNS_SERVER="localhost:443"
export HOMEDNS_VERIFY=false  # don't verify https certificates from the server
export JWT_SUBJECT="0aaa1111-1111-1a1a-a111-aa11aa11111a"
export JWT_KEY="./jwt-key.pem"
export JWT_AUDIENCE="homedns-api"
export JWT_ISSUER="homedns-clients"
```

## Get an existing `A RECORD`
Assuming you've configured environment variables to connect and authenticate with the
server, the command to get a record becomes very simple:

```shell
homedns-api A GET "example.com"
```

## Create an `A RECORD`
To create a domain `A` record, that will tell clients to resolve `example.com` to `104.18.74.230`

```shell
homedns-api A CREATE "example.com" --address "104.18.74.230" --ttl 300
```

> **Note:** `example.com` is a real domain, however that doesn't matter. 
> All records will be served as AUTHORITATIVE and will tell clients to direct 
> themselves to whatever address you specify.  
> HomeDNS will act as the authority for all records created within it, regardless of if they are real domains.

The `ttl` setting if you are unfamiliar tells clients how often (in seconds) they should check to see if 
the dns record is changed. Usually keeping this number small is fine especially when you are hosting a nameserver
for yourself.  You should never go below a value of 30 seconds.

## Delete an `A RECORD`
To delete the record created in the above example is very simple.

```shell
homedns-api A DELETE "example.com"
```

> **Note:** Multiple A records can exist for a single domain name. This command will delete all records associated
> with the domain specified.


## Update an `A RECORD`
Updating an `A` record is nearly identical to the command to create it.

```shell
homedns-api A UPDATE "example.com" --address "104.18.74.230" --ttl 300
```

## Upsert an `A RECORD`
What if you don't know a record exists and you want to update it or create it.  
That is exactly what upsert does.

Upsert should always succeed.

```shell
homedns-api A UPSERT "example.com" --address "104.18.74.230" --ttl 300
```