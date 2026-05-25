# Barcode Structure

Barcodes need to be supported for multiple object types. The most fundamental 
object type is boards, so board serial numbers are referenced as the raw number 
with no prefix.

It's likely we'll want to use barcodes to represent many things in addition to 
objects, such as operations to perform. An example is "go into relocation mode 
so that the next barcode I scan is taken to be an asset, which is to have its 
location updated to that indicated by the barcode I scan next". Or a batch 
version of that, scanning a location first and then multiple objects.

Should we use prefixes or some other structure to ensure that we can differentiate 
between object types represented by barcodes?

The most fundamental object type is boards, so board serial numbers are referenced
as the raw number with no prefix.

It could be something similar to the way LCSC works, wwhere they prefix every 
component with "C".

Could be:

 * Sxxxx / xxxx (serial)
 * Dxxxx (design)
 * Oxxxx (organisation)
 * Lxxxx (location)
 * Bxxxx (batch)
 * Uxxxx (user)
 * Cxxxx (command)
 * Pxxxx (part)
 * Gxxxx (group of parts, eg: reel, bag, etc)
 
The actual number could be the database index of the record, or it could be 
an arbitrary number. For example, we could print a roll of barcodes starting 
as "G1234" and incrementing, and then put them on reels. Each reel would have 
its barcode added to its record as an attribute but not as the primary key.
