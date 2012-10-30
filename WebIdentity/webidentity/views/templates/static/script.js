/*
 * <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */
$(function() {

    $('#personas-info .persona-select').addClass('hidden');

    $('#personas-info').tabs('#personas-info div.pane', {
        tabs: 'h3',
        effect: 'slide',
        initialIndex: null
    });

    $('#personas-info h3').click(function (e) {
        var $input, isChecked;
        $input = $(this).next().find('.persona-select > input');
        isChecked = $input.is(':checked');
        // Uncheck all items.
        $('#personas-info').find('input[type=radio]').removeAttr('checked');
        $('#personas-info').find('h3 > span').hide();
        if (!isChecked) {
            $input.attr('checked', 'checked');
            $(this).children('span').show();
        }
    });

});
