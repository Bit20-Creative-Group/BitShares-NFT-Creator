# A Standard for NFTs on the BitShares Blockchain

## What makes an NFT

* Singular or very small integral issuance:
  * Asset precision should be zero
  * Asset should have a max_supply of 1 or of a very small limited number
* Immutability
  * BitShares assets have a disavowable permission to increase max supply. This permission must be disavowed by the issuer, else there remians a mechanism to increase issuance.
  * Asset descriptions — important metadata that uniquely identifies the digital entity encaspulated by the NFT is stored in the Asset Description field.  Since this field is mutable, the possibility exists for the asset issuer to alter, deface, spoil, or otherwise destroy the NFT.  At present, there is no disavowable asset permission for editing the description.  For obvious reasons, it would be useful if there was one, to safeguard the NFT data, however there is not.  An alternative, however, once the NFT is created, is to transfer asset issuership of the NFT to `null-account`, whereby future asset update operations will become impossible.

## Asset Description Langauge

The asset `description` field can accomodate arbitrary text.  Current convention is to store a JSON blob allowing asset issuers to embed three distinct descriptive properties of the asset.  This JSON blob has the following form:  (whitespace added for visual clarity)

```
{
  "main": "A magical asset that you will surely want to HODL",
  "market": "BTS",
  "short_name": "Magical Asset"
}
```

Where the fields have the following meanings:

| | |
|--------|---------|
| `main` | Main asset description. Asset issuers can write basically whatever they want. |
| `market` | "SYMBOL" — Client software uses this symbol to indicate a preferred, suggested, or defualt market this asset should trade against. |
| `short_name` | A short (max 32 chars) name of the asset.  (E.g. "Bitcoin", for asset BTC.) |
| | |

To create a NFT, this document proposes the addition of two new fields to this JSON blob.   The keys are `nft_object` and `nft_signature`, so that the blob will now have the following form:

```
{
  "main": "A magical asset that you will surely want to HODL",
  "market": "BTS",
  "nft_object": { ... },
  "nft_signature": "20ff....ea",
  "short_name": "Magical Asset"
}
```

with the following meanings:

| | |
|--------|---------|
| `nft_object` | A JSON object containing NFT content and attributes, in a format and containing fields as described below |
| `nft_signature` | A signature (ECDSA or similar) from a well-known public key of the artist. The artist signs the ascii serialization of the contents of the `nft_object` to obtain the signature. Client software can verify that the signature is valid. |
| | |

## NFT Object

The NFT object shall be represented as a canonicalized JSON blob containing all the of required fields and some combination of the optional fields described below.  A canonicalized JSON blob is an ascii JSON serialization in which keys appear in lexicographically sorted order, and in which all non-quoted whitespace is removed (no space between keys and values, no linebreaks, no indentation, etc.). Additionally, quoted text should escape control sequences and special characters (such as linebreaks, tabs, unicode characters, etc.).

### Required keys:

All of the following are required:

| | |
|-|-|
| `type` | Should be one of {"NFT/ART", ... (others t.b.d.)} |
| `title` | Title of the work |
| `artist` | Name or pseudonym of the artist. May also include aliases or online names or handles, to include blockchain account names or addresses which might faciliate authenticating a signing key. Example: "Arty McArtface (on BitShares as @artface)" |
| `attestation` | Here the artist commits or dedicates the artwork to the blockchain, expressly naming the token name or ID under which the work will live, and attests to it's uniquness, e.g. that no other NFT encapsulation exists. (If a piece is a reissue, then the phrasing here should indicate as such. It can then be known that it is a *secondary* rendition, without risk of being confused with the original.) |
| `encoding` | Typically "base64", and indicates that the binary data of the media item has been serialized to ascii using base64 encoding |
| `narrative` | A personal statement from the artist describing the work, such as what the work means to them, or what inspired it.  May include details of it's creation, etc.  It's a freeform field, and can be adapted as appropriate for the piece.  Example, if the work is an avatar, playing card, role playing character, etc., then this field may also include stats and abilities, strengths, weaknesses, etc.  |
| | |


### Media item keys:

ONE of the following keys must be included to embed the media item if the value of the `type` field is "NFT/ART".  The particular key used indicates the file type.  Note, the data contained in the value is encoded according to the value of the required `encoding` key, unless the key is a multihash key, in which case the `encoding` key can be ignored.

| | |
|-|-|
| `image_png` | An image file in PNG format |
| `image_gif` | An image file in GIF format |
| `image_jpeg` | An image file in JPEG format |
| `image_png_multihash` | An ipfs multihash of an image file in PNG format |
| `image_gif_multihash` | An ipfs multihash of an image file in GIF format |
| `image_jpeg_multihash` | An ipfs multihash of an image file in JPEG format |
| | |

### Optional Keys:

| | |
|-|-|
| `password_multihash` | If the media item and/or narrative fields are encrypted, e.g. with AES encryption, this field can contain the ipfs multihash of a file containing either the unlock passphrase or other instructions for how to decrypt the work. (Note that ipfs multihashes can be computed *without* necessarily publishing, so that this multihash provides a mechanism to reveal the decryption keys at a future date, and publish in such a way that an NFT viewer can easily retrieve the needed information for rendering. A standardized format for these password files is T.B.D.) |
| | |