# BitShares NFT Creator (BNFTC)

Create, audit, and deploy NFT tokens on the BitShares blockchain.  This tool creates tokens following the Bit20 Creative Group's [BitShares NFT Specification](https://github.com/Bit20-Creative-Group/BitShares-NFT-Specification), and may or may not be compatible with *other* NFT specifications.

This particular NFT creator tool is geared towards creating visual artwork NFT's and can embed images such as PNG, JPEG, and GIF images.

This tool is a console based python tool, and assumes you have [Python3](https://www.python.org) installed and have some basic familiarity with working from the command line.  Familiarity with [JSON](https://www.w3schools.com/js/js_json_intro.asp) is also very helpful.  (JSON is a machine-parsable but still human-readable format for representing object data. It is used to define the properties of your NFT.)

#### Caveat Emptor:

*Please note that this tool is still quite rough-around-the-edges, and comes with absolutely no guarantees or warranties. Use at your own risk.*

## Install

#### Dependencies:

The only dependency is [uptick](https://pypi.org/project/uptick/), which will bring along with it several python libraries to enable working with the BitShares blockchain.  This dependency can be installed with pip:

```
pip3 install uptick
```

If this succeeds, you should have what you need to run BNFTC.  If it fails, see uptick installation instructions at: https://pypi.org/project/uptick/.

#### Install:

From a suitable directory:

```
git clone https://github.com/Bit20-Creative-Group/BitShares-NFT-Creator.git
```

## Usage

```
cd BitShares-NFT-Creator
python3 ./cli.py nft --help
```

The latter command will list subcommands under the `nft` category and give some general help.  For help on a specific subcommand, issue that subcommand with the `--help` flag.  E.g.:

```
python3 ./cli.py nft template --help
```

This will give help on the `nft template` subcommand. This is the subcommand you should start with. It will create a blank NFT template, and even prepopulate some of the fields if you provide optional flags listed in the help output.  Each command will generally guide you in the direction of the next command.

#### Usage on testnet:

BNFT will accept the `--node` option, just like `uptick` does.  Use it as:

```
python3 ./cli.py --node ws://api.some.where/ nft [subcommand] [...]
```

To use BNFTC on testnet, simply make sure you provide an api address for a testnet api node.

## Workflow

There are numerous steps in the design stage, before you get to the publish stage where you actually create the token.  This give plenty of opportunity to get the details right.

### Create image file:

First step is to create an image file to embed in your NFT.  Save the file as `TOKENNAME_media.png`, where TOKENNAME is the name of the token (or asset symbol) to which the NFT will be deployed. Also, the file extension doesn't have to be `png`, several other formats are also supported.

### Create a template file:

The `nft template` command will create a template for you to start editing.  You can specify some options on the command line to prepopulate some template fields, if you desire.  This command will produce the file `TOKENNAME_template.json`.

```
python3 ./cli.py nft template --title "My Artwork Title" --artist "Famous Artist" MYTOKEN
```

This results in the following output:

```
Wrote MYTOKEN_template.json.
Template file has been written. Edit to fill in needed
details and follow up with 'nft makeobject' command.
```

Next open up `MYTOKEN_template.json` in a text editor suitable for editing JSON data and begin filling in the details of your NFT. The file contains two broad sections, "asset", and "nft".  The "asset" section describes blockchain attributes of the token, and also lets you sepcify some aspects of the deployment process (like who the token should be first issued to).  The "nft" section defines the real "meat" of the NFT and contains the artistic content such as image data, title, artist name, a brief "narrative", and license and other data.  The "nft" section will be used to produce the `nft_object` blob which the artist must digitally sign, and the "asset" section will control details of the deployment process.

### Make object file:

The next step is to use the `nft makeobject` command to produce the `nft_object` JSON blob which represents the "meat" of the NFT. This will produce a JSON file containing "cononicalized" JSON (this removes all excess whitespace and lexically sorts the keys in the JSON object), and will inlcude within the JSON a base64 encoding of the image file.  The command is run as so:

```
python3 ./cli.py nft makeobject MYTOKEN
```

This will produce file `MYTOKEN_object.json`.

Once this file is produced, the artist will need to produce a digital signature on the contents of this file.

### Validate the object file

The validate command inspects the object blob for correctness and checks the digital signature (if present).

```
python3 ./cli.py nft validate MYTOKEN
```

This will produce output similar to:

```
Validation Results for MYTOKEN_object.json:

  * JSON is valid and can be deserialized:          Pass!!
  * JSON is in canonical form:                      Pass!!
  * Required keys are present:                      Pass!!
  * Attestation explicitly mentions token symbol:   Pass!!
  * Signature is valid:                           **FAILED**
        Signature is empty
```

Since in the above example, we haven't signed the object blob yet, the signature validation shows as failed.  If all other tests are passing, we can procede to the signing step.

### Sign the object file

The signature is an important part of the NFT as it allows proof of intent to publish the NFT to be established, and, if the artist signs with a well-known public key or address (e.g. a Bitcoin address), then it allows viewers of the NFT to confirm authenticity.

The needed signature can be produced with BNFTC, or with an external tool.  BNFTC knows how to produce and verify BitShares ECDSA signatures, and can verify (though not produce) Bitcoin "signed message" sigantures.  The ability to use Bitcoin signatures means that artists with an established identity on platforms such as Counterparty can sign their works on BitShares with their well-known Counterparty addresses. Other types of signatures may also be used (e.g. PGP signatures) and may be valid within the spec, though BNFTC doesn't yet know how to verify them.

Once the signature is produced, it is important to run `nft validate` again to make sure the signature validates.

#### Signing with BNFTC:

A typical scenario would be to sign the NFT with the memo key of the artist's BitShares account.  To do this, BNFTC needs access to the corresponding private key in WIF format.  This should be stored in a single-line ascii text file, named, e.g., `privatekey.wif`.  (WARNING: Be sure you are working on a secure computer that no one else has access to.)  In the template file, there is an entry "wif_file", and it's value should be set to the name of this file.  Then you can sign the NFT object with:

```
python3 ./cli.py nft sign MYTOKEN
```

This will respond with:

```
Wrote MYTOKEN_sig.txt.
A signature file was written.
Next steps: validate and finalize the asset.
```

The signature was written to the file `MYTOKEN_sig.txt`.

#### Signing with an external tool:

The contents of the file `MYTOKEN_object.json` are the message that needs to be signed.  This file can be opened in a text editor, copied, and pasted into a message signing tool, such as can be found in many Bitcoin or Counterparty wallets.  Be sure that the text editor does not change the file in any way.  The file is a single-line canonicalized JSON blob with no line break at the end.  It needs to be copied and pasted exactly.

When the signature is produced, create a file `MYTOKEN_sig.txt` and paste the signature into this file.  The file should contain *nothing* but the signature itself.  Most signature tools will produce output that is either base16 ("hex") or base64 encoded.  Either is fine and van be interpreted by BNFTC.

A Notable Caveat: The "Sign Message" feature within the BitShares GUI does NOT work for this purpose, as it adds additional metadata to the message before signing, which unfortunately does not lend itself to embedding into an NFT token.  So if signing with a BitShares memo key, it is recommended at this time to use BNFTC to produce the signature.

### Finalize the NFT

This command compiles the NFT object blob, signature, asset description, and other asset properties into a single JSON blob that is used in the next steps for asset deployment.

```
python3 ./cli.py nft finalize MYTOKEN
```

Response looks like:

```
Wrote MYTOKEN_final.json.
An asset deployment file was written. Please inspect for correctness,
but note that this file is in canonical form - DO NOT EDIT!
If changes are needed, delete MYTOKEN_final.json and repeat some
or all of the steps above.
Next steps: inspect and deploy the asset.
```

### Inspect the finalized NFT

This command inspects the finalized NFT with a few more checks to make sure it is ready for deployment.  Alternatively, if the asset already exists on the network, this command inspects the existing asset.  Thus it should be used both before deployment, to confirm that NFT is ready, and after, to confirm successful deployment.

```
python3 ./cli.py nft inspect MYTOKEN
```

### Deploy the NFT

The `nft deploy` command is used to deploy the NFT (create the token and populate its description and attributes) on the BitShares network.

```
python3 ./cli nft deploy --help
```

...for more information.

Note that if you are deploying through a gallery, (i.e. as a subasset of a gallery token), then you should get explicit deployment instructions through them.
