import base64
import json
import sys


def getEmptyTemplate():
    return {
        "type":"NFT/ART",
        "title":"Put title here",
        "artist":"Artist name here (alias/handle)",
        "narrative":"Artist describes work here.",
        "attestation":"\
I, [artist's name], originator of the work herein, \
hereby commit this piece of art to the BitShares blockchain, \
to live as the token named [TOKEN.NAME], and attest that \
no prior tokenization of this art exists or has been authorized \
by me. The work is original, and is fully mine to dedicate in this way. \
May it persevere until the end of time.",
        }


def makeTemplateFromFile(filename, templatefile=None, canonicalize=False):

    if not templatefile:
        template = getEmptyTemplate()
    else:
        template = json.load(open(templatefile))

    if filename:
        b64 = base64.b64encode(open(filename,"rb").read()).decode('ascii')
        key_suff = filename.split('.')[-1:][0]
        key = "image_"+(key_suff or "data")

        template.update({
            key: b64,
            "encoding":"base64"
        })

    if canonicalize==False:
        out = json.dumps(template, indent=2)
    else:
        out = json.dumps(template, separators=(',',':'), sort_keys=True)

    return out


def wrapWithSig(jsonblobstring, sigstring, shortname, market):
    return ('{' +
            '"main":"NFT Token %s"'%shortname +
            ',"market":"%s"'%market +
            ',"object":' + jsonblobstring +
            ',"short_name":"%s"'%shortname +
            ',"signature":"' + sigstring +
            '"}'
            )

def printUsage():

    print("[python3] nftpack.py [image.png [template.json [signature [\"Short Name\" [MARKET]]]]]")
    print()
    print("If run with no arguments, print sample template (below).")
    print("Save template to a file and fill out all fields.")
    print("If run with two args, will insert image into json template, and ")
    print("canonicalize the json blob for signing.")
    print("If run with three args, the third arg is the signature (typically ")
    print("a hex string but can be any string). The json blob will be ")
    print("wrapped in a container that embeds the signature. Use this for ")
    print("the asset description field.")
    print()
    print("Copy the following into a json file:\n")


if __name__ == "__main__":

    imgfile = sys.argv[1] if len(sys.argv) > 1 else None
    jsonfile = sys.argv[2] if len(sys.argv) > 2 else None
    canonical = True if jsonfile else False
    sigstring = sys.argv[3] if len(sys.argv) > 3 else None
    shortname = sys.argv[4] if len(sys.argv) > 4 else None
    preferred = sys.argv[5] if len(sys.argv) > 5 else None

    if len(sys.argv) == 1:
        printUsage()
        # continue, do not exit

    out = makeTemplateFromFile(imgfile, jsonfile, canonical)

    header="-----BEGIN MESSAGE-----"
    footer="-----END MESSAGE-----"
    if sigstring:
        out = wrapWithSig(out, sigstring, shortname, preferred)
        header="-----BEGIN ASSET DESCRIPTION-----"
        footer="-----END ASSET DESCRIPTION-----"

    if sys.stdout.isatty():
        print(header)
        print(out)
        print(footer)
    else:
        print(out)
