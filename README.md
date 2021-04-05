# BitShares-NFT-Creator
Create a NFT on BitShares

***WARNING: USE ONLY ON TESTNET FOR NOW!  This is an evolving tool, following an evolving spec. As such, it may, and indeed likely will, produce results incompatible with the final spec.***

## Install

#### Dependencies:

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

To use  BNFTC on testnet, simply make sure you provide an api address for a testnet api node.
