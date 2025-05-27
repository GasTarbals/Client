from telethon.tl import types
from typing import Dict, Optional, Union


class MediaHandler:
    """Класс для обработки медиа вложений из Telegram."""

    def get_media_info(self, media: Union[types.MessageMediaPhoto, types.MessageMediaDocument,
    types.MessageMediaWebPage, types.MessageMediaContact,
    types.MessageMediaGeo, types.MessageMediaVenue,
    types.MessageMediaGame, types.MessageMediaInvoice]) -> Dict:
        """Получение информации о медиа.

        Args:
            media: Объект медиа из Telegram

        Returns:
            Словарь с информацией о медиа или пустой словарь если тип не поддерживается
        """
        if isinstance(media, types.MessageMediaPhoto):
            return self._handle_photo(media)
        elif isinstance(media, types.MessageMediaDocument):
            return self._handle_document(media)
        elif isinstance(media, types.MessageMediaWebPage):
            return self._handle_webpage(media)
        elif isinstance(media, types.MessageMediaContact):
            return self._handle_contact(media)
        elif isinstance(media, (types.MessageMediaGeo, types.MessageMediaGeoLive)):
            return self._handle_geo(media)
        elif isinstance(media, types.MessageMediaVenue):
            return self._handle_venue(media)
        elif isinstance(media, types.MessageMediaGame):
            return self._handle_game(media)
        elif isinstance(media, types.MessageMediaInvoice):
            return self._handle_invoice(media)
        return {}

    def _handle_photo(self, media: types.MessageMediaPhoto) -> Dict:
        """Обработка фото."""
        return {
            'type': 'photo',
            'id': getattr(media.photo, 'id', None),
            'access_hash': getattr(media.photo, 'access_hash', None),
            'date': getattr(media.photo, 'date', None),
            'sizes': [{
                'type': type(size).__name__,
                'w': getattr(size, 'w', None),
                'h': getattr(size, 'h', None)
            } for size in getattr(media.photo, 'sizes', [])],
            'dc_id': getattr(media.photo, 'dc_id', None),
            'has_stickers': getattr(media.photo, 'has_stickers', False)
        }

    def _handle_document(self, media: types.MessageMediaDocument) -> Dict:
        """Обработка документов."""
        doc = media.document
        return {
            'type': 'document',
            'id': getattr(doc, 'id', None),
            'access_hash': getattr(doc, 'access_hash', None),
            'file_reference': getattr(doc, 'file_reference', None),
            'date': getattr(doc, 'date', None),
            'mime_type': getattr(doc, 'mime_type', None),
            'size': getattr(doc, 'size', None),
            'dc_id': getattr(doc, 'dc_id', None),
            'attributes': [{
                'type': type(attr).__name__,
                **self._parse_document_attribute(attr)
            } for attr in getattr(doc, 'attributes', [])],
            'thumbs': [{
                'type': type(thumb).__name__,
                'w': getattr(thumb, 'w', None),
                'h': getattr(thumb, 'h', None)
            } for thumb in getattr(doc, 'thumbs', [])] if hasattr(doc, 'thumbs') else None
        }

    def _parse_document_attribute(self, attr) -> Dict:
        """Парсинг атрибутов документа."""
        if isinstance(attr, types.DocumentAttributeFilename):
            return {'file_name': attr.file_name}
        elif isinstance(attr, types.DocumentAttributeAnimated):
            return {'animated': True}
        elif isinstance(attr, types.DocumentAttributeSticker):
            return {
                'alt': attr.alt,
                'stickerset': getattr(attr, 'stickerset', None),
                'emoji': getattr(attr, 'emoji', None)
            }
        elif isinstance(attr, types.DocumentAttributeVideo):
            return {
                'duration': attr.duration,
                'w': attr.w,
                'h': attr.h,
                'round_message': getattr(attr, 'round_message', False),
                'supports_streaming': getattr(attr, 'supports_streaming', False)
            }
        elif isinstance(attr, types.DocumentAttributeAudio):
            return {
                'duration': attr.duration,
                'voice': getattr(attr, 'voice', False),
                'title': getattr(attr, 'title', None),
                'performer': getattr(attr, 'performer', None),
                'waveform': getattr(attr, 'waveform', None)
            }
        elif isinstance(attr, types.DocumentAttributeImageSize):
            return {'w': attr.w, 'h': attr.h}
        return {}

    def _handle_webpage(self, media: types.MessageMediaWebPage) -> Dict:
        """Обработка веб-страниц."""
        return {
            'type': 'webpage',
            'id': getattr(media.webpage, 'id', None),
            'url': getattr(media.webpage, 'url', None),
            'display_url': getattr(media.webpage, 'display_url', None),
            'title': getattr(media.webpage, 'title', None),
            'description': getattr(media.webpage, 'description', None)
        }

    def _handle_contact(self, media: types.MessageMediaContact) -> Dict:
        """Обработка контактов."""
        return {
            'type': 'contact',
            'phone_number': media.phone_number,
            'first_name': media.first_name,
            'last_name': media.last_name,
            'user_id': media.user_id,
            'vcard': getattr(media, 'vcard', None)
        }

    def _handle_geo(self, media: Union[types.MessageMediaGeo, types.MessageMediaGeoLive]) -> Dict:
        """Обработка геолокации."""
        geo = {
            'type': 'geo_live' if isinstance(media, types.MessageMediaGeoLive) else 'geo',
            'long': media.geo.long,
            'lat': media.geo.lat,
            'access_hash': getattr(media.geo, 'access_hash', None)
        }
        if isinstance(media, types.MessageMediaGeoLive):
            geo.update({
                'heading': getattr(media, 'heading', None),
                'period': media.period
            })
        return geo

    def _handle_venue(self, media: types.MessageMediaVenue) -> Dict:
        """Обработка места."""
        return {
            'type': 'venue',
            'geo': self._handle_geo(media.geo),
            'title': media.title,
            'address': media.address,
            'provider': media.provider,
            'venue_id': media.venue_id,
            'venue_type': media.venue_type
        }

    def _handle_game(self, media: types.MessageMediaGame) -> Dict:
        """Обработка игры."""
        return {
            'type': 'game',
            'id': media.game.id,
            'access_hash': media.game.access_hash,
            'short_name': media.game.short_name,
            'title': media.game.title,
            'description': media.game.description
        }

    def _handle_invoice(self, media: types.MessageMediaInvoice) -> Dict:
        """Обработка платежного инвойса."""
        return {
            'type': 'invoice',
            'title': media.title,
            'description': media.description,
            'currency': media.currency,
            'total_amount': media.total_amount,
            'start_param': media.start_param,
            'photo': self._handle_webpage(media.webphoto) if media.webphoto else None
        }