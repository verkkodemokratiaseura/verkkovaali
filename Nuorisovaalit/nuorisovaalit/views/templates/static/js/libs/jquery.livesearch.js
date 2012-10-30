/*
 * <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */
jQuery.fn.liveUpdate = function(list){
	list = jQuery(list);

	if ( list.length ) {
		var rows = list.find('li.candidate > a'),
			cache = rows.map(function(){
				return this.innerHTML.toLowerCase();
			});
			
		this
			.keyup(filter).keyup()
			.parents('form').submit(function(){
				return false;
			});
	}
		
	return this;
		
	function filter(){
		var term = jQuery.trim( jQuery(this).val().toLowerCase() ), scores = [];
		rows.removeClass('search-hit');
		
		if ( term ) {

			cache.each(function(i){
				var score = this.score(term);
				if (score > 0) { scores.push([score, i]); }
			});

			jQuery.each(scores.sort(function(a, b){return b[0] - a[0];}), function(){
				jQuery(rows[ this[1] ]).addClass('search-hit');
			});
		}
	}
};
