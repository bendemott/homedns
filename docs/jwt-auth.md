# JWT Authentication
This document describes how to obtain credentials and authenticate clients with JWT.

Json Web Token or `jwt` is an authentication mechanism that ensures communication between
a client and server is secure and protects from replay or spoofing attacks.
Because each request is signed with a private key, impersonating an API user with an api token
is not possible.

The **HomeDNS** Server employs `JWT` authentication by default.

## Server Configuration
Configuring `JWT` Settings on the server is discussed in [jwt-configuration](jwt-configuration.md)

## JWT Concepts
A JWT Token is generating when the client authenticates. In the case of this application
we generate an `authorization` header that is sent along with each request.

The `authorization` token sends several pieces of information.

- `subject` (`sub`) - The subject is the identity of the user performing the API request.
  - `--jwt-subject` is the subject CLI Argument
- `jwt-key` - The key defines a file containing a `PEM` encoding private key. You'll read more about this below
  - `--jwt-key` is the jwt private key CLI Argument
- ``

## Obtaining JWT Credentials from the Server
- The server keeps a list of all valid jwt subjects that are allowed to connect to it.
- You can use the Servers command line interface to manage jwt subjects and tokens.
- When you add a new subject to the server a subject name will be generated automatically.
  This name is a `uuid` string. 
- The server will generate a encryption key pair that contains a public and private key at the same time the `subject` 
  Is add to the server.
  - The private key is shown only once, it will be printed to the screen, this is your client password for JWT
  - You must save this private key to a text file for safe keeping, the server keeps no record of the private key.
  - A public key is kept on the server. This public key is used to decrypt client requests made.
  - The subject name is how the server identifies you and knows which public key to use to decrypt your request.
  
### Generate JWT Credentials
On the server where `homedns` is running / installed we can use the command-line to add JWT subjects to its list
of valid credentials.

It should be noted, the server does not need to be running to add subjects to it, these commands MUST BE RUN
locally on the server. You cannot add JWT credentials remotely via the API.

Type the command below to generate a jwt credential and add it to the server.

```shell
homedns-jwt add
```

When run this command will output your subject and private key:
```shell
JWT CREDENTIALS GENERATED

>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
SUBJECT: 0aaa1111-1111-1a1a-a111-aa11aa11111a
>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
>>>>>>> PRIVATE KEY, COPY AND SAVE SECURELY FOR CLIENT SIDE AUTH >>>>>>>>
>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC9mGP15vn3jrRl
EGOGus/hnxWdYOKvoNLj+7tATrPvHHuGQmsrZLRfTQw0Cf78d0Ureabg2N9WlfbI
aN+3haUC0G+rQozPeHEca87RojV7afRgqoFZsfjkW79jgG5l0zTAXjTJHdjY/hzb
v7NY+kKgFRnx9HYvOWe112Ehc3WIzSnSDKRXPO9SqvOxLMkPJUrUR248E0qN8p4b
vRzQXA2rBN4liYmo71J5I/EIanlm6LWe2lc9LJkvoDYv2vYbA8nN423X0iGrGv3G
K8Nthcw6A+2eS2smj9oO+nKms3GWDN6vN0BPwSEvJDuY7A9UFk3VcWf0O6q1qF34
1db//vczAgMBAAECggEAAvpxW4wI0jQ6Ljo/Lf8iQ9uRZdr/RJ4EohMywlRaLD/o
ytehQlm/IZ4eunSLvmCLRB8RmYeenogVi9ll5kahrHUkw+50MtAkCrvA0Hc5Wtpz
vc7/4C5VCBVO4NvEIDJcqkbwklY3MVVwk50jzpqD0Gr0cOITtzMyJ1+eRX3AU2lK
uitqkn8EgYiidooo0khO67D6eFpQ11osv0tm3Bh/tfYiQy8v3uYLRbhZw7f50i5S
b3ydkTq1T6MNVxdh5Dw6tNp1pz+ub3n2VMAO/WaBju14wjA2/AKxqeiPw2bco9sh
CmjkOtAoGQBKrrN+iQ+ELDyC5JGURfn9V05yc7WieQKBgQDgOM0LEQgm9j/+2BAG
a13yUKH3p3NeicFG4naw92TGv8KI8XcDDl1rROfP2iYIzPUhdCfp0gQbZlnXEISS
GtZtHyTc5Q6gXeh2YcSDhFJRXJJ1qhmFGN7gvs4qYC/r8BpW4rme9hq5b6Y7VH5k
kONdnQ5FpuVDKgFygcdfd2zpCQKBgQDYd0UiL44tTlVSzMXi+wcT4goh0/aIgkL4
nVNQPxPr6uy8kZUvbPYSh8Fq5HqDtaRZp2O2MQbJiwS62Aot4w2r/Gkl+IYp21Wj
cD4JNwi4TTXd/aaahx6XcDHVpneTZRp3gGqSoMvZ+FbqQyQgvXeC/mcUmw1WIAoO
03zvGiRZWwKBgH20mo/nvpBJYlt3upQ+wW7GceesQ2vvAyLAeBaCvEcI3wFzjmty
NEGdYfEPtl8cuRlGS9I04gSSfy+pnQlkbm7DFSGacXbK7zbfXRL2rkfbBGlfMeuC
pAGQN3leb79w3vNzLOnHw/fOdn2wwyOSb0XedU/rX4EmHaWayLHm/HIxAoGBAJ+l
JxmVVRhY41iTqYZDeO7TEIHuX65B076j2SQfwUOHGV3hSNOXWsxDzwRUyX6F4lY0
u7dM5SKTIsPiPW+mOxkSqUHVzqzkFH7bcwU8z3ONjiLQxaTF7mvl1PsrMJlGQYTM
8sx9RprVKtTO+8AhvBiiI8fwqp9QNdrFYyi8cP5tAoGAAfvkA24Q4pOcTtHyGtpD
wM46t/Lh7T885gT9l8RZOd6xgX8zmrAmeORhT4B6DDrUyQvXBA5Zs9W8ewgsem64
QoFjdAy0WOxRL6INKQOSmEny2c4cSGaG+75qaZ2n2pWQ+clTvxCb5BiKbYYEyjGW
QIcsjtx7vBBDW+ndpSibHUw=
-----END PRIVATE KEY-----


Subject added to "/etc/homedns/jwt_secrets/jwt_subjects.yaml"
Public Key save to "/etc/homedns/jwt_secrets/98e9e059-6f65-494f-a0ad-e36cf78958fa.crt"
```

Before closing your terminal its very important you take not of the subject - this is your user id.
I suggest saving it to file
```
echo "0aaa1111-1111-1a1a-a111-aa11aa11111a" > homedns-sub.txt
```

You must copy the private key contents and save them to file as well.

starting with and including  
- `-----BEGIN PRIVATE KEY-----`  

up to and including 
- `-----END PRIVATE KEY-----`

## Listing JWT Credentials

You can list valid JWT subjects and when they are created with the following command.  

```shell
homedns-jwt list
```

## Removing JWT Access
You can remove access for a single JWT Subject with the `remove` command.

```shell
homedns-jwt remove 98e9e059-6f65-494f-a0ad-e36cf78958fa
```

## Client Authentication
All CLI Commands that require JWT authentication accept command line arguments.

For example the client cli command to echo back the ip address of client can be authenticated to
using jwt with the following set of arguments:
```shell
homedns-api \
    --server localhost:443 \
    --no-verify \
    --jwt-subject=<jwt-subject> \
    --jwt-key <private-key-file.pem> \
    IP4
```
## JWT Environment Variables
It can be laborious with many requests to specify jwt arguments for every command.
So instead you can specify environment variables that will do the work for you.

A special command will help you setup your environment the `ENV` command.  
My passing in our authentication values as normal, we can authenticate let
the cli authenticate to the server, verify our connection and then generate
the statements needed to setup our environment.

```shell
homedns-api \
    --server localhost:443 \
    --no-verify \
    --jwt-subject "0aaa1111-1111-1a1a-a111-aa11aa11111a" \
    --jwt-key "./key.pem" \
    ENV
```

Output

```shell
Copy and Paste these into your shell:
=======================================
export HOMEDNS_SERVER="localhost:443"
export HOMEDNS_VERIFY=false
export JWT_SUBJECT="0aaa1111-1111-1a1a-a111-aa11aa11111a"
export JWT_KEY="./jwt-key.pem"
export JWT_AUDIENCE="homedns-api"
export JWT_ISSUER="homedns-clients"
```

All you have to do is copy the lines that begin with `export` paste them into your shell,
and now you can issue a command without the fuss of specifying the server, or your jwt credentials
each time.

For example, the command we typed before now becomes

```shell
homedns-api IP4
```