// Copyright SmartBear Software
// SPDX-License-Identifier: Apache-2.0
package models

import (
	pb "github.com/opentelemetry/opentelemetry-demo/src/product-catalog/genproto/oteldemo"
	"gorm.io/gorm"
	"gorm.io/gorm/clause"
)

type Product struct {
	ID            string `gorm:"primaryKey"`
	Name          string
	Description   string
	Picture       string
	ProductPrices []ProductPrice `gorm:"foreignKey:ProductID"`
	Categories    []Category     `gorm:"many2many:product_categories;"`
}

type ProductPrice struct {
	ID        uint   `gorm:"primaryKey"`
	Currency  string `gorm:"uniqueIndex:idx_price"`
	ProductID string `gorm:"uniqueIndex:idx_price"`
	Units     uint
	Nanos     uint `gorm:"default:0"`
}

type Category struct {
	ID   uint `gorm:"primaryKey"`
	Name string
}

type ProductCategory struct {
	ProductID  Product  `gorm:"primaryKey"`
	CategoryID Category `gorm:"primaryKey"`
}

func (m *Product) AfterDelete(tx *gorm.DB) (err error) {
	tx.Clauses(clause.Returning{}).Where("product_id = ?", m.ID).Delete(&ProductPrice{})
	tx.Clauses(clause.Returning{}).Where("product_id = ?", m.ID).Delete(&ProductCategory{})
	return
}

func (m *Category) AfterDelete(tx *gorm.DB) (err error) {
	tx.Clauses(clause.Returning{}).Where("category_id = ?", m.ID).Delete(&ProductCategory{})
	return
}

func (p *Product) ToProto() *pb.Product {
	protoProduct := &pb.Product{
		Id:          p.ID,
		Name:        p.Name,
		Description: p.Description,
		Picture:     p.Picture,
	}

	for _, cat := range p.Categories {
		protoProduct.Categories = append(protoProduct.Categories, cat.Name)
	}

	for _, price := range p.ProductPrices {
		if price.Currency == "USD" {
			protoProduct.PriceUsd = &pb.Money{
				CurrencyCode: price.Currency,
				Units:        int64(price.Units),
				Nanos:        int32(price.Nanos),
			}
			break
		}
	}

	return protoProduct
}
