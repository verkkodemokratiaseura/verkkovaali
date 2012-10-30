/*
 * <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */
/* Author: 

*/
$(function() {
    if (!Modernizr.input.autofocus) {
        $('input[autofocus]').focus();
    }
    
    /* Build the data for the candidate search */
    var candidates = [];
    $('li.candidate > a').each(function(index) {
        // Give each candidate an id we can link to
        $candidate = $(this);
        $candidate.attr({'id': 'candidate-' + index});
        candidates.push({
            'title': $candidate.text(),
            'anchor': '#candidate-' + index});
    });

    /* Activate the candidate search */
    if (candidates.length > 0) {
        $('#candidate-search').autocomplete(candidates, {
            autoFill: false,
            multiple: false,
            matchContains: true,
            cacheLength: 1000,
            max: 25,
            width: 250,
            scroll: false,
            highlight: false,
            formatItem: function (item) { return item.title; }
            }).result(function (event, item) {
                $('li.candidate > a').removeClass('search-hit');
                $(item.anchor).addClass('search-hit');
                location.href = item.anchor;
            });
    }
    
    /* Create window close buttons */
    $('.exit')
        .live('click', function () {console.log("Closing window")})
        .replaceWith('<form><input type="button" class="exit" title="Poistu äänestyksestä" value="Poistu äänestyksestä" /></form>')
});
