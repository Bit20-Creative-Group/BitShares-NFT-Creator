import click
import base64
import json
import sys
import re
from bitshares.account import Account
from bitshares.amount import Amount
from bitshares.asset import Asset
from bitshares.price import Price
from .decorators import online, unlock
from .main import main, config
from .ui import print_tx, format_tx, print_table, print_message


@main.group()
def nft():
    """ Tools for NFTs

    Creation:

    General sequence: Create template files with `nft template`. Edit
    those template files, make an object file with `nft makeobject`.
    Sign object with GPG or with `nft sign`. Add signature to job
    template. Check that job validates with `nft validate`. Make
    description file with `nft finalize`. Deploy with `nft deploy`.

    Inspecting:

    (looking up NFT's already on chain...)

    """
    pass


def _valid_SYMBOL_or_throw(symbol):
    if symbol.upper() == symbol and re.match(r"^[A-Z][A-Z0-9\.]{2,15}$", symbol):
        return
    else:
        raise Exception("Invalid SYMBOL.")


@nft.command()
@click.argument("token")
@click.option(
    "--title", help="Title of the artwork. (Will also be used as coin's " +
    "short_name up to 32 chars.)",
    default="My NFT Art"
)
@click.option(
    "--artist", help="Artists name or identity",
    default="Some Great Artist"
)
@click.option(
    "--market", help="SYMBOL of coin this NFT trades against"
)
@click.option(
    "--echo", is_flag=True,
    help="Echo template to stdout in addition to writing files."
)
@click.pass_context
def template(ctx, token, title, artist, market, echo):
    """ Write template files to begin NFT creation.

    Writes template files for you to fill in to begin the process
    of NFT creation.
    """
    _valid_SYMBOL_or_throw(token)

    short_name = title[0:32] # short_name field limit in Ref UI supposedly

    job_template = {
        "token": token,
        "quantity": 1,
        "short_name": short_name,
        "description": title + " is a nonfungible artwork token by " +
                       artist + " on the BitShares blockchain.",
        "market": market,
        "whitelist_market": "",
        "media_file": token+"_media.png",
        "media_embed": True,
        "media_multihash": "",
        "nft_signature": "ADD_SIG_HERE_WHEN_SIGNED",
    }
    out_job_template = json.dumps(job_template, indent=2)

    nft_template = {
        "type": "NFT/ART",
        "title": title,
        "artist": artist,
        "narrative": "Artist describes work here.",
        "attestation": "\
I, " + artist + ", originator of the work herein, \
hereby commit this piece of art to the BitShares blockchain, \
to live as the token named " + token + ", and attest that \
no prior tokenization of this art exists or has been authorized \
by me. The work is original, and is fully mine to dedicate in this way. \
May it preserve until the end of time.",
    }
    out_nft_template = json.dumps(nft_template, indent=2)

    if echo:
        print(out_job_template)
        print(out_nft_template)

    files_written = 0

    out_job_file = token+"_job.json"
    try:
        with open(out_job_file, "x") as f:
            f.write(out_job_template)
            f.write("\n")
            print("Wrote " + out_job_file + ".")
            files_written += 1
    except FileExistsError:
        print("ERROR: File "+out_job_file+" already exists. NOT overwriting!")
    except IOError:
        print("ERROR: Could not write file "+out_job_file)

    out_nft_file = token+"_nft.json"
    try:
        with open(out_nft_file, "x") as f:
            f.write(out_nft_template)
            f.write("\n")
            print("Wrote " + out_nft_file + ".")
            files_written += 1
    except FileExistsError:
        print("ERROR: File "+out_nft_file+" already exists. NOT overwriting!")
    except IOError:
        print("ERROR: Could not write file "+out_nft_file)

    if files_written == 2:
        print("Template files have been written. Edit to fill in needed")
        print("details and follow up with 'nft makeobject' command.")
    else:
        print("Some files were not written. Check files and try again.")


@nft.command()
@click.argument("token")
@click.option(
    "--echo", is_flag=True,
    help="Echo template to stdout in addition to writing files."
)
@click.pass_context
def makeobject(ctx, token, echo):
    """ Write a canonicalized nft_object blob.

    Reads [TOKEN]_job.json, [TOKEN]_nft.json, and the referenced media
    file, and productes a canonicalized nft_object blob suitable for
    signing.
    """
    _valid_SYMBOL_or_throw(token)

    job_file = token+"_job.json"
    nft_file = token+"_nft.json"

    job_data = json.load(open(job_file))
    nft_data = json.load(open(nft_file))

    media_file = job_data["media_file"]
    key_suff = media_file.split('.')[-1:][0]
    media_key = "image_"+(key_suff or "data")
    media_mh_key = "image_"+(key_suff or "data")+"_multihash"

    if job_data.get("media_embed",True):
        b64 = base64.b64encode(open(media_file,"rb").read()).decode('ascii')
        nft_data.update({
            media_key: b64,
            "encoding":"base64",
        })

    if job_data["media_multihash"]:
        nft_data.update({
            media_mh_key: job_data["media_multihash"],
        })

    out_object = json.dumps(nft_data, separators=(',',':'), sort_keys=True)
    if echo:
        print(out_object)

    files_written = 0
    out_obj_file = token+"_object.json"
    try:
        with open(out_obj_file, "x") as f:
            f.write(out_object)
            print("Wrote " + out_obj_file + ".")
            files_written += 1
    except FileExistsError:
        print("ERROR: File "+out_obj_file+" already exists. NOT overwriting!")
    except IOError:
        print("ERROR: Could not write file "+out_job_file)

    if files_written == 1:
        print("An NFT object file was written. Please inspect for correctness, but")
        print("note that this file is in canonical form for signing - DO NOT EDIT!")
        print("If changes are needed, delete " + out_obj_file + " and repeat steps")
        print("above, editing the _job.json or _nft.json file instead.")
        print("Next steps: validate and digitally sign the object file.")
    else:
        print("Some files were not written. Check files and try again.")


VALIDATIONS = [
    "JSON is valid and can be deserialized",
    "JSON is in canonical form",
    "Required keys are present",
    "Attestation explicitly mentions token symbol",
    "Signature is valid",
]

def _validate_nft_object(obj_json_str, token):
    """ Validate json serialization of an NFT object.

    Returns a vector of bools correlated to the VALIDATIONS list.
    """
    ret = [False] * len(VALIDATIONS)
    remarks = [[]] * len(VALIDATIONS)
    ival = -1

    ## Validation: JSON
    ival += 1
    try:
        obj = json.loads(obj_json_str)
        ret[ival] = True
    except:
        return ret

    ## Validation: JSON Canonical
    ival += 1
    result = True
    rems = []
    if obj_json_str[0] != '{':
        result = False
        rems.append("Invalid leading character, check whitespace")
    if obj_json_str[-1] != '}':
        result = False
        rems.append("Invalid trailing character, check whitespace")
    if "\n" in obj_json_str:
        result = False
        rems.append("File contains line breaks")
    ret[ival] = result
    remarks[ival] = rems

    ## Validation: Required JSON Keys
    ival += 1
    result=True
    rems = []
    for key in ["title", "artist", "attestation", "narrative"]:
        if key not in obj:
            result = False
            rems.append("Missing JSON key: "+key)
    # TODO: Check for image keys
    ret[ival] = result
    remarks[ival] = rems

    ## Validation: Attestation
    ival += 1
    if len(token) >= 3 and token in obj["attestation"]:
        ret[ival] = True

    ## Validation: Signature
    ival += 1
    ret[ival] = False # DUMMY

    return (ret, remarks)


@nft.command()
@click.argument("token")
@click.option(
    "--echo", is_flag=True,
    help="Echo template to stdout in addition to writing files."
)
@click.pass_context
def validate(ctx, token, echo):
    """ Validate an nft_object blob.

    Reads [TOKEN]_object.json and subjects to a battery of tests.
    """
    _valid_SYMBOL_or_throw(token)

    obj_file = token+"_object.json"
    with open(obj_file,"rb") as f:
        obj_string = f.read().decode('utf-8')

    (validations, remarks) = _validate_nft_object(obj_string, token)

    PassFail = {True: "  Pass!!", False: "**FAILED**"}
    fieldwidth = max([len(i) for i in VALIDATIONS])+1

    print("Validation Results for "+obj_file+":\n")
    for i in range(len(validations)):
        tmplt = "  * %%-%ds %%s"%fieldwidth
        print(tmplt%(VALIDATIONS[i]+":", PassFail[validations[i]]))
        for rem in remarks[i]:
            print("        "+rem)
    print()


@nft.command()
@click.argument("token")
@click.option(
    "--echo", is_flag=True,
    help="Echo to stdout in addition to writing files."
)
@click.pass_context
def finalize(ctx, token, echo):
    """ Compile nft asset description.

    Compile nft object, signature, and asset metadata into a complete
    asset decription suitable for embedding into token.

    Reads [TOKEN]_object.json and writes [TOKEN]_final.json.
    """
    _valid_SYMBOL_or_throw(token)

    job_file = token+"_job.json"
    obj_file = token+"_object.json"

    job_data = json.load(open(job_file))
    obj_data = json.load(open(nft_file))

    desc_data = {
        "main": job_data["description"],
        "short_name": job_data["short_name"],
        "market": job_data["market"],
        "nft_object": obj_data,
        "nft_signature": job_data["nft_signature"],
    }

    out_desc = json.dumps(desc_data, separators=(',',':'), sort_keys=True)
    if echo:
        print(out_desc)

    files_written = 0
    out_desc_file = token+"_final.json"
    try:
        with open(out_desc_file, "x") as f:
            f.write(out_desc)
            print("Wrote " + out_desc_file + ".")
            files_written += 1
    except FileExistsError:
        print("ERROR: File "+out_desc_file+" already exists. NOT overwriting!")
    except IOError:
        print("ERROR: Could not write file "+out_desc_file)

    if files_written == 1:
        print("An asset description file was written. Please inspect for correctness,")
        print("but note that this file is in canonical form - DO NOT EDIT!")
        print("If changes are needed, delete " + out_desc_file + " and repeat some")
        print("or all of the steps above.")
        print("Next steps: inspect and deploy the asset.")
    else:
        print("Some files were not written. Check files and try again.")


@nft.command()
@click.argument("token")
@click.pass_context
def inspect(ctx, token):
    """ Inspect and validate an ASSET.

    Inspect and validate an ASSET on chain or an ASSET_final.json file.
    """
    _valid_SYMBOL_or_throw(token)

    # TODO: ...
