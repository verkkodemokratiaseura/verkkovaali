# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
def parse_districts(seats, municipalities):
    """Parses the voting district -> municipality mappings for a file."""

    # Read the number of seats per district info first.
    numseats = {}
    for line in open(seats).readlines()[1:]:
        code, nseats, _ = line.split(None, 2)
        numseats[int(code)] = int(nseats)

    data = open(municipalities).readlines()
    districts = {}

    # There are four lines of headers in the file which need to be skipped.
    for line in data[4:]:
        _, municipality, code, district = line.strip().split("\t", 3)
        name = district.strip().decode('iso-8859-15')
        code = int(code)

        districts.setdefault((name, code, numseats[code]), set()).add(
            municipality.strip().decode('iso-8859-15'))

    return districts
